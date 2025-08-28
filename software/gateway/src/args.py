import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='ThingsBoard Edge Gateway', )
    parser.add_argument('--tb-host')
    parser.add_argument('--tb-port', type=int)

    return parser.parse_args()
