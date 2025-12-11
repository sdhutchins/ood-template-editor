#!/usr/bin/env bash

echo "Hello, {{ user_name | default('friend') }}!"
echo "Today is {{ day_of_week | default('some day') }}."

echo "Running on host: {{ host | default('unknown') }}"
