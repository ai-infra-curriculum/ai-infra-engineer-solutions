// CUDA kernel: element-wise vector add.
#include <cuda_runtime.h>

__global__ void add_kernel(int n, const float * __restrict__ a,
                            const float * __restrict__ b, float * __restrict__ c) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) c[i] = a[i] + b[i];
}

extern "C" void launch_add(int n, const float* a, const float* b, float* c) {
    int block = 256;
    int grid = (n + block - 1) / block;
    add_kernel<<<grid, block>>>(n, a, b, c);
}
