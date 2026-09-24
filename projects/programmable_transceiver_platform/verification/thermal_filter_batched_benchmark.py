"""Run the shared repeated-step benchmark with the batched integrator."""
from thermal_filter_guard_benchmark import main as run_benchmark
from thermal_filter_batched import batched_step


def main():
    run_benchmark(batched_step, report_name='thermal-filter-batched-benchmark.json',
                  extra_sources=('thermal_filter_batched.py', 'thermal_filter_batched_benchmark.py'))


if __name__ == '__main__':
    main()
