cmake_minimum_required(VERSION 3.16)
project(cpp_perf_regression LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)
set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "Disable Google Benchmark's own tests")
set(BENCHMARK_ENABLE_GTEST_TESTS OFF CACHE BOOL "Disable Google Benchmark's GTest tests")
FetchContent_Declare(
    googlebenchmark
    GIT_REPOSITORY https://github.com/google/benchmark.git
    GIT_TAG v1.9.1
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(googlebenchmark)

add_executable(perfbench_samples
    benchmarks/sample_benchmarks.cpp
)
target_link_libraries(perfbench_samples PRIVATE benchmark::benchmark)
