#!/usr/bin/env python3
import sys
from performance.driver.core.cli.entrypoints import dcos_perf_test_driver
sys.exit(dcos_perf_test_driver(sys.argv[1:]))
