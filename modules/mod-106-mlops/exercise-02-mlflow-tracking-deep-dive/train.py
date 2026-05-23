"""Training with autolog + custom metrics + signature + packaged pyfunc."""
import mlflow
import mlflow.sklearn
import numpy as np
from mlflow.models.signature import infer_signature
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split


mlflow.set_experiment("iris-classifier")
mlflow.sklearn.autolog()


def main():
    X, y = load_iris(return_X_y=True)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)

    with mlflow.start_run(run_name="rf-200-12") as run:
        model = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=0)
        model.fit(Xtr, ytr)
        preds = model.predict(Xte)

        # Custom metrics beyond what autolog captures
        mlflow.log_metric("f1_macro", f1_score(yte, preds, average="macro"))
        for cls in np.unique(y):
            mask = yte == cls
            mlflow.log_metric(f"acc_class_{cls}", accuracy_score(yte[mask], preds[mask]))

        # Custom artifact
        with open("notes.md", "w") as f:
            f.write("trained on macbook m3 pro; full iris dataset")
        mlflow.log_artifact("notes.md")

        # Explicit signature (instead of autolog inferring)
        signature = infer_signature(Xte, preds)
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            signature=signature,
            input_example=Xte[:3],
            registered_model_name="iris-rf",
        )
        print(f"run_id={run.info.run_id}")


if __name__ == "__main__":
    main()
