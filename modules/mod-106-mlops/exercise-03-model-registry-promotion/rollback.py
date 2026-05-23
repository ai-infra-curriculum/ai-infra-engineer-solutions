"""Roll back to the previous Production version, if any."""
import argparse

from mlflow.tracking import MlflowClient


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name")
    args = p.parse_args()

    client = MlflowClient()
    versions = client.search_model_versions(f"name='{args.name}'")
    # Sort by version desc; find current Production, then next-most-recent
    versions.sort(key=lambda v: int(v.version), reverse=True)
    current = next((v for v in versions if v.current_stage == "Production"), None)
    previous = next((v for v in versions[versions.index(current) + 1:]
                      if v.current_stage in ("Staging", "Archived")), None) if current else None

    if not current or not previous:
        raise SystemExit("No rollback target available")

    client.transition_model_version_stage(args.name, current.version, "Archived")
    client.transition_model_version_stage(args.name, previous.version, "Production")
    print(f"rolled back {args.name}: v{current.version} → Archived, v{previous.version} → Production")


if __name__ == "__main__":
    main()
