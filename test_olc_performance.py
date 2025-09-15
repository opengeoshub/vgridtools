#!/usr/bin/env python3
"""
Test script to demonstrate OLC grid performance improvements.
This script compares the original and optimized implementations.
"""

import time
import sys
import os

# Add the plugin directory to the path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from processing_provider.generator.olc_grid_optimized import (
        olc_grid_optimized,
        olc_grid_within_bbox_optimized,
        olc_grid_ids_optimized,
    )
    from vgrid.generator.olcgrid import olc_grid, olc_grid_within_bbox, olc_grid_ids

    print("✓ Successfully imported both original and optimized functions")
except ImportError as e:
    print(f"✗ Import error: {e}")
    print("Make sure you're running this from the plugin directory")
    sys.exit(1)


def benchmark_function(func, *args, **kwargs):
    """Benchmark a function and return execution time and result."""
    start_time = time.time()
    try:
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return execution_time, result, None
    except Exception as e:
        end_time = time.time()
        execution_time = end_time - start_time
        return execution_time, None, str(e)


def test_global_grid_performance():
    """Test global grid generation performance."""
    print("\n" + "=" * 60)
    print("TESTING GLOBAL GRID GENERATION PERFORMANCE")
    print("=" * 60)

    # Test with resolution 2 (small dataset)
    resolution = 2

    print(f"\nTesting with resolution {resolution}:")
    print("-" * 40)

    # Test original implementation
    print("Original implementation:")
    time_orig, result_orig, error_orig = benchmark_function(
        olc_grid, resolution, verbose=False
    )
    if error_orig:
        print(f"  ✗ Error: {error_orig}")
    else:
        print(f"  ✓ Time: {time_orig:.3f} seconds")
        print(f"  ✓ Generated {len(result_orig)} cells")

    # Test optimized implementation
    print("Optimized implementation:")
    time_opt, result_opt, error_opt = benchmark_function(
        olc_grid_optimized, resolution, verbose=False
    )
    if error_opt:
        print(f"  ✗ Error: {error_opt}")
    else:
        print(f"  ✓ Time: {time_opt:.3f} seconds")
        print(f"  ✓ Generated {len(result_opt)} cells")

    # Calculate speedup
    if not error_orig and not error_opt and time_orig > 0:
        speedup = time_orig / time_opt
        print(f"\n🚀 Speedup: {speedup:.2f}x faster")
        if speedup > 1.1:
            print("✅ Significant performance improvement!")
        elif speedup > 1.0:
            print("✅ Modest performance improvement")
        else:
            print("⚠️  No significant improvement")


def test_bbox_grid_performance():
    """Test bbox grid generation performance."""
    print("\n" + "=" * 60)
    print("TESTING BBOX GRID GENERATION PERFORMANCE")
    print("=" * 60)

    # Test with a small bbox and higher resolution
    resolution = 4
    bbox = [-74.0, 40.7, -73.9, 40.8]  # Small area in NYC

    print(f"\nTesting with resolution {resolution} and bbox {bbox}:")
    print("-" * 40)

    # Test original implementation
    print("Original implementation:")
    time_orig, result_orig, error_orig = benchmark_function(
        olc_grid_within_bbox, resolution, bbox
    )
    if error_orig:
        print(f"  ✗ Error: {error_orig}")
    else:
        print(f"  ✓ Time: {time_orig:.3f} seconds")
        print(f"  ✓ Generated {len(result_orig)} cells")

    # Test optimized implementation
    print("Optimized implementation:")
    time_opt, result_opt, error_opt = benchmark_function(
        olc_grid_within_bbox_optimized, resolution, bbox, verbose=False
    )
    if error_opt:
        print(f"  ✗ Error: {error_opt}")
    else:
        print(f"  ✓ Time: {time_opt:.3f} seconds")
        print(f"  ✓ Generated {len(result_opt)} cells")

    # Calculate speedup
    if not error_orig and not error_opt and time_orig > 0:
        speedup = time_orig / time_opt
        print(f"\n🚀 Speedup: {speedup:.2f}x faster")
        if speedup > 1.1:
            print("✅ Significant performance improvement!")
        elif speedup > 1.0:
            print("✅ Modest performance improvement")
        else:
            print("⚠️  No significant improvement")


def test_ids_only_performance():
    """Test ID-only generation performance."""
    print("\n" + "=" * 60)
    print("TESTING ID-ONLY GENERATION PERFORMANCE")
    print("=" * 60)

    resolution = 2

    print(f"\nTesting with resolution {resolution} (IDs only):")
    print("-" * 40)

    # Test original implementation
    print("Original implementation:")
    time_orig, result_orig, error_orig = benchmark_function(olc_grid_ids, resolution)
    if error_orig:
        print(f"  ✗ Error: {error_orig}")
    else:
        print(f"  ✓ Time: {time_orig:.3f} seconds")
        print(f"  ✓ Generated {len(result_orig)} IDs")

    # Test optimized implementation
    print("Optimized implementation:")
    time_opt, result_opt, error_opt = benchmark_function(
        olc_grid_ids_optimized, resolution, verbose=False
    )
    if error_opt:
        print(f"  ✗ Error: {error_opt}")
    else:
        print(f"  ✓ Time: {time_opt:.3f} seconds")
        print(f"  ✓ Generated {len(result_opt)} IDs")

    # Calculate speedup
    if not error_orig and not error_opt and time_orig > 0:
        speedup = time_orig / time_opt
        print(f"\n🚀 Speedup: {speedup:.2f}x faster")
        if speedup > 1.1:
            print("✅ Significant performance improvement!")
        elif speedup > 1.0:
            print("✅ Modest performance improvement")
        else:
            print("⚠️  No significant improvement")


def main():
    """Run all performance tests."""
    print("OLC Grid Performance Test")
    print("Comparing original vs optimized implementations")

    try:
        test_global_grid_performance()
        test_bbox_grid_performance()
        test_ids_only_performance()

        print("\n" + "=" * 60)
        print("PERFORMANCE TEST SUMMARY")
        print("=" * 60)
        print("✅ All tests completed!")
        print("\nKey optimizations implemented:")
        print("• Caching of step size calculations")
        print("• Spatial indexing for faster intersection queries")
        print("• Vectorized operations using NumPy")
        print("• Parallel processing for large datasets")
        print("• Early termination conditions")
        print("• Memory-efficient generators")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
