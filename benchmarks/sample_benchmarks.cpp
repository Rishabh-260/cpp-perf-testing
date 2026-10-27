#include <benchmark/benchmark.h>

#include <algorithm>
#include <cstdint>
#include <numeric>
#include <random>
#include <unordered_map>
#include <vector>

namespace {

void BM_VectorAccumulate(benchmark::State& state) {
    const auto size = static_cast<std::size_t>(state.range(0));
    std::vector<std::uint64_t> values(size);
    std::iota(values.begin(), values.end(), 1);

    for (auto _ : state) {
        const auto sum = std::accumulate(values.begin(), values.end(), std::uint64_t{0});
        benchmark::DoNotOptimize(sum);
    }
    state.SetBytesProcessed(static_cast<std::int64_t>(state.iterations()) *
                            static_cast<std::int64_t>(size * sizeof(values.front())));
}
BENCHMARK(BM_VectorAccumulate)->Range(1 << 10, 1 << 16);

void BM_HashLookup(benchmark::State& state) {
    const auto size = static_cast<std::size_t>(state.range(0));
    std::unordered_map<std::uint64_t, std::uint64_t> values;
    values.reserve(size);
    for (std::size_t i = 0; i < size; ++i) {
        values.emplace(i, i * 3);
    }

    std::uint64_t key = 0;
    for (auto _ : state) {
        key = (key + 7919) % size;
        benchmark::DoNotOptimize(values.at(key));
    }
}
BENCHMARK(BM_HashLookup)->Range(1 << 10, 1 << 16);

}  // namespace

BENCHMARK_MAIN();
