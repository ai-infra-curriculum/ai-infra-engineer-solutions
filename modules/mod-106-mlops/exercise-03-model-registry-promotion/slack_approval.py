"""Production promotion requires explicit Slack approval (sketch)."""
import argparse
import os

import httpx


def request_approval(name: str, version: str) -> str:
    """Post to Slack; return Slack message_ts so we can listen for reactions."""
    payload = {
        "channel": "#ml-platform",
        "text": (
            f"Approval needed: promote *{name}* v{version} to Production.\n"
            f"React with :+1: to approve, :-1: to reject."
        ),
    }
    r = httpx.post("https://slack.com/api/chat.postMessage", json=payload,
                    headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"})
    r.raise_for_status()
    return r.json()["ts"]


def wait_for_approval(message_ts: str, channel: str = "C12345678") -> bool:
    """In production: poll reactions API every 30s or use Events API.
    Returns True on :+1: from an approved approver, False on :-1:."""
    # Real implementation would poll; sketch returns True immediately.
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("version")
    p.add_argument("--to", required=True)
    args = p.parse_args()

    if args.to != "production":
        print("Slack approval only required for production"); return
    ts = request_approval(args.name, args.version)
    if wait_for_approval(ts):
        print(f"approved → invoking promote.py")
    else:
        print("rejected")


if __name__ == "__main__":
    main()
