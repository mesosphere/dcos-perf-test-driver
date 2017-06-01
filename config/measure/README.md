# Measurement Fragments

This directory contains the configuration fragments that define what to measure and how to measure it.

## Files

### `deployment-time.yml`

Measures `deploymentTime` metric, as the duration between a `HTTPResponseEndEvent` and `MarathonDeploymentSuccessEvent` event.

Use this to track the time a deployment takes from the moment of the HTTP request completion.

### `http-request-time.yml`

Measures `httpRequestTime` metric, as the duration between a `HTTPRequestStartEvent` and `HTTPResponseEndEvent` event.

Use this to track how long the REST API reqests take to complete.
