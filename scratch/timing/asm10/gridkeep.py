def keep(off, n=40):
    """assembly 70 um phase rule (TIM-26): 27 um Metal5 channels at x = 12.25 / 47.25 + 70k from the block's left edge"""
    return [(off + ax + 70 * k - 13.5, off + ax + 70 * k + 13.5) for k in range(-1, n) for ax in (12.25, 47.25)]
