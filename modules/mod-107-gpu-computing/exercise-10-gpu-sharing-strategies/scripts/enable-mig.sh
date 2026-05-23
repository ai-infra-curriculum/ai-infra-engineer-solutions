#!/usr/bin/env bash
# Enable MIG mode + create representative instances.
# Run on the host (requires root).
set -euo pipefail

sudo nvidia-smi -mig 1
sudo nvidia-smi mig -cgi 1g.5gb,1g.5gb,2g.10gb -C
nvidia-smi mig -lgi
