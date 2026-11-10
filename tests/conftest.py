import os
# Exercise rate limits in dedicated middleware tests; do not throttle fixture conversions.
os.environ['RATE_LIMIT_PER_MINUTE'] = '0'
