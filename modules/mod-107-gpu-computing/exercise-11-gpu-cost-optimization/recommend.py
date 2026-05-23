"""Produce a final recommendation document."""
import subprocess


def main():
    out = subprocess.run(["python", "cost_model.py"], capture_output=True, text=True)
    print("# GPU Cost Recommendation")
    print()
    print("## Cost model output\n```")
    print(out.stdout)
    print("```\n")
    print("## Recommendations")
    print("""
1. **Real-time inference (W1)**: stay on L40S reserved 3yr. Right-sized for latency, steady demand.
2. **Batch overnight (W2)**: Spot A100. Save ~60% vs on-demand. Restart-tolerant pipeline.
3. **LLM 24/7 (W3)**: L40S reserved 3yr; Mistral-7B fp16 fits comfortably.
4. **Training (W4)**: NVLink-equipped A100 nodes; on-demand for resilience. Reserve only if duty cycle > 60%.
5. **Experimentation (W5)**: MIG slice of a shared dev L40S; serverless GPU for true ad-hoc.

## Risks
- Spot interruption can spike rerun cost; add 20-30% buffer.
- 3-year reservation assumes utilization stays steady; review quarterly.
- VRAM doesn't equal performance; pick by both throughput AND memory fit.
""")


if __name__ == "__main__":
    main()
