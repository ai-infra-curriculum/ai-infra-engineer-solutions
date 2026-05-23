from setuptools import setup
from torch.utils.cpp_extension import BuildExtension, CUDAExtension


setup(
    name="my_ops",
    ext_modules=[
        CUDAExtension(
            name="my_ops",
            sources=["my_ops.cpp", "vector_add.cu"],
        ),
    ],
    cmdclass={"build_ext": BuildExtension},
)
