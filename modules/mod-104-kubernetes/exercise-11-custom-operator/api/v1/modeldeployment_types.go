package v1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

type ModelDeploymentSpec struct {
	ModelURI    string `json:"modelURI"`
	Image       string `json:"image"`
	Replicas    int32  `json:"replicas,omitempty"`
	MinReplicas int32  `json:"minReplicas,omitempty"`
	MaxReplicas int32  `json:"maxReplicas,omitempty"`
	TargetCPU   int32  `json:"targetCPU,omitempty"`
	Resources   struct {
		CPU    string `json:"cpu,omitempty"`
		Memory string `json:"memory,omitempty"`
		GPU    int32  `json:"gpu,omitempty"`
	} `json:"resources,omitempty"`
}

type ModelDeploymentStatus struct {
	ReadyReplicas int32  `json:"readyReplicas"`
	Phase         string `json:"phase"`
	Endpoint      string `json:"endpoint,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status
type ModelDeployment struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`
	Spec              ModelDeploymentSpec   `json:"spec,omitempty"`
	Status            ModelDeploymentStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true
type ModelDeploymentList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []ModelDeployment `json:"items"`
}
