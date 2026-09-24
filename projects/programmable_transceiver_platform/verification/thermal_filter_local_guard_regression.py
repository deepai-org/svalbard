"""Local-guard variant of the shared seeded thermal-filter regression."""
from thermal_filter_batched_regression import main as run_regression

def main():
    return run_regression(local_guard=True)

if __name__=='__main__':main()
