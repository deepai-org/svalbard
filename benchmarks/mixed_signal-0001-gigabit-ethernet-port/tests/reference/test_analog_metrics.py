#!/usr/bin/env python3
"""Known-answer and hostile-input tests for analog metric extraction."""

from analog_metrics import center_sample_eye, common_mode, differential, threshold_crossings


def assert_close_vector(observed: list[float], expected: list[float], tolerance: float = 1e-12) -> None:
    assert len(observed) == len(expected)
    assert all(abs(a - b) <= tolerance for a, b in zip(observed, expected))


def main() -> None:
    vp = [1.8, 2.0, 1.7, 1.6]
    vn = [1.5, 1.4, 1.6, 1.8]
    assert_close_vector(differential(vp, vn), [0.3, 0.6, 0.1, -0.2])
    assert_close_vector(common_mode(vp, vn), [1.65, 1.7, 1.65, 1.7])

    bits = [0, 1, 0, 1]
    diff = [-0.30, -0.25, -0.35, -0.30, 0.30, 0.27, 0.35, 0.30,
            -0.28, -0.22, -0.31, -0.29, 0.32, 0.29, 0.36, 0.31]
    eye = center_sample_eye(diff, bits, 4)
    assert abs(eye.eye_height_v - 0.66) < 1e-12
    assert eye.sample_count == 4

    crossings = threshold_crossings([0.0, 1.0, 2.0], [-1.0, 1.0, -1.0])
    assert crossings == [0.5, 1.5]

    for invalid in (([], [], 4), ([0.0, 1.0], [0], 1), ([0.0] * 4, [1], 4)):
        try:
            center_sample_eye(*invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid eye fixture was accepted")

    print("analog metric self-test: PASS")


if __name__ == "__main__":
    main()
