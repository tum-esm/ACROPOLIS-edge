import argparse

def parse_args():
    parser = argparse.ArgumentParser(
        prog='ACROPOLIS Gateway',
    )
    parser.add_argument('--tb-host')
    parser.add_argument('--tb-port', type=int)

    return parser.parse_args()

