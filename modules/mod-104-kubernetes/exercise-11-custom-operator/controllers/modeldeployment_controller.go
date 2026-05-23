package controllers

import (
	"context"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	autoscalingv2 "k8s.io/api/autoscaling/v2"
	"k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/util/intstr"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"

	mlv1 "github.com/me/model-operator/api/v1"
)

type ModelDeploymentReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

func (r *ModelDeploymentReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	var md mlv1.ModelDeployment
	if err := r.Get(ctx, req.NamespacedName, &md); err != nil {
		return ctrl.Result{}, client.IgnoreNotFound(err)
	}

	if err := r.reconcileDeployment(ctx, &md); err != nil {
		return ctrl.Result{}, err
	}
	if err := r.reconcileService(ctx, &md); err != nil {
		return ctrl.Result{}, err
	}
	if err := r.reconcileHPA(ctx, &md); err != nil {
		return ctrl.Result{}, err
	}

	// Update status
	var dep appsv1.Deployment
	if err := r.Get(ctx, client.ObjectKey{Name: md.Name, Namespace: md.Namespace}, &dep); err == nil {
		md.Status.ReadyReplicas = dep.Status.ReadyReplicas
		md.Status.Phase = "Ready"
		md.Status.Endpoint = "http://" + md.Name + "." + md.Namespace + ".svc.cluster.local"
		_ = r.Status().Update(ctx, &md)
	}
	return ctrl.Result{}, nil
}

func (r *ModelDeploymentReconciler) reconcileDeployment(ctx context.Context, md *mlv1.ModelDeployment) error {
	replicas := md.Spec.Replicas
	if replicas == 0 {
		replicas = 1
	}
	dep := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{Name: md.Name, Namespace: md.Namespace},
	}
	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, dep, func() error {
		dep.Spec.Replicas = &replicas
		dep.Spec.Selector = &metav1.LabelSelector{MatchLabels: map[string]string{"app": md.Name}}
		dep.Spec.Template = corev1.PodTemplateSpec{
			ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"app": md.Name}},
			Spec: corev1.PodSpec{
				Containers: []corev1.Container{{
					Name:  "model",
					Image: md.Spec.Image,
					Env: []corev1.EnvVar{
						{Name: "MODEL_URI", Value: md.Spec.ModelURI},
					},
					Ports: []corev1.ContainerPort{{ContainerPort: 8000, Name: "http"}},
					Resources: corev1.ResourceRequirements{
						Requests: corev1.ResourceList{
							corev1.ResourceCPU:    resource.MustParse(defaultStr(md.Spec.Resources.CPU, "100m")),
							corev1.ResourceMemory: resource.MustParse(defaultStr(md.Spec.Resources.Memory, "256Mi")),
						},
					},
				}},
			},
		}
		return controllerutil.SetControllerReference(md, dep, r.Scheme)
	})
	return err
}

func (r *ModelDeploymentReconciler) reconcileService(ctx context.Context, md *mlv1.ModelDeployment) error {
	svc := &corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: md.Name, Namespace: md.Namespace}}
	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, svc, func() error {
		svc.Spec.Selector = map[string]string{"app": md.Name}
		svc.Spec.Ports = []corev1.ServicePort{
			{Port: 80, TargetPort: intstr.FromString("http"), Name: "http"},
		}
		return controllerutil.SetControllerReference(md, svc, r.Scheme)
	})
	return err
}

func (r *ModelDeploymentReconciler) reconcileHPA(ctx context.Context, md *mlv1.ModelDeployment) error {
	if md.Spec.MinReplicas == 0 || md.Spec.MaxReplicas == 0 {
		return nil
	}
	hpa := &autoscalingv2.HorizontalPodAutoscaler{
		ObjectMeta: metav1.ObjectMeta{Name: md.Name, Namespace: md.Namespace},
	}
	target := md.Spec.TargetCPU
	if target == 0 {
		target = 70
	}
	_, err := controllerutil.CreateOrUpdate(ctx, r.Client, hpa, func() error {
		hpa.Spec.ScaleTargetRef = autoscalingv2.CrossVersionObjectReference{
			APIVersion: "apps/v1", Kind: "Deployment", Name: md.Name,
		}
		hpa.Spec.MinReplicas = &md.Spec.MinReplicas
		hpa.Spec.MaxReplicas = md.Spec.MaxReplicas
		hpa.Spec.Metrics = []autoscalingv2.MetricSpec{{
			Type: autoscalingv2.ResourceMetricSourceType,
			Resource: &autoscalingv2.ResourceMetricSource{
				Name: corev1.ResourceCPU,
				Target: autoscalingv2.MetricTarget{
					Type:               autoscalingv2.UtilizationMetricType,
					AverageUtilization: &target,
				},
			},
		}}
		return controllerutil.SetControllerReference(md, hpa, r.Scheme)
	})
	if errors.IsAlreadyExists(err) {
		return nil
	}
	return err
}

func defaultStr(s, d string) string {
	if s == "" {
		return d
	}
	return s
}

func (r *ModelDeploymentReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&mlv1.ModelDeployment{}).
		Owns(&appsv1.Deployment{}).
		Owns(&corev1.Service{}).
		Owns(&autoscalingv2.HorizontalPodAutoscaler{}).
		Complete(r)
}
