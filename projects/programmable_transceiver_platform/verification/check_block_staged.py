"""Staged block FIFO scoreboard with overwrite-while-stalled mutation."""
from check_block_elastic import main

if __name__ == '__main__':
    main(staged=True)
