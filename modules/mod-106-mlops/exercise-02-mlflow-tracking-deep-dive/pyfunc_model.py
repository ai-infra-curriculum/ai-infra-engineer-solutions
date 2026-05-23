"""Wrap a sklearn model + custom preprocessing as an mlflow.pyfunc.PythonModel."""
import mlflow
import mlflow.pyfunc
import numpy as np


class IrisModel(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        from joblib import load
        self.model = load(context.artifacts["model"])

    def predict(self, context, model_input):
        # Custom preprocessing: clip outliers
        X = np.clip(model_input, 0, 10)
        preds = self.model.predict(X)
        return {"label": preds, "label_name": ["setosa", "versicolor", "virginica"][preds[0]]}


def main():
    mlflow.pyfunc.log_model(
        artifact_path="iris-pyfunc",
        python_model=IrisModel(),
        artifacts={"model": "models/rf.joblib"},
        registered_model_name="iris-pyfunc",
        pip_requirements=["scikit-learn>=1.5", "joblib>=1.3", "numpy>=1.26"],
    )


if __name__ == "__main__":
    main()
