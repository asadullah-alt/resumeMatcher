#!/bin/bash
TARGET_ENV=${1:-development}
export ENV=$TARGET_ENV
python3 -m app.main
