// PyTorch CUDA extension wrapper.
#include <torch/extension.h>

extern "C" void launch_add(int n, const float* a, const float* b, float* c);

torch::Tensor add(torch::Tensor a, torch::Tensor b) {
    TORCH_CHECK(a.is_cuda(), "a must be on CUDA");
    TORCH_CHECK(b.is_cuda(), "b must be on CUDA");
    TORCH_CHECK(a.sizes() == b.sizes(), "shape mismatch");
    TORCH_CHECK(a.dtype() == torch::kFloat32, "float32 only");

    auto c = torch::empty_like(a);
    launch_add(a.numel(),
                a.data_ptr<float>(), b.data_ptr<float>(),
                c.data_ptr<float>());
    return c;
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("add", &add, "Vector add (CUDA)");
}
