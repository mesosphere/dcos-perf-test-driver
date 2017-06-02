# Library Fragments

This folder contains various configuration fragments that are included by the performance tests.

## Files

### `marathon-observers.yml`

<table>
    <tr>
        <th>Uses Definitions:</th>
        <td>
            <code>marathon_url</code>
        </td>
    </tr>
</table>

Defines the shared observers for all marathon configurations.

### `marathon-config-local-sim.yml`

<table>
    <tr>
        <th>Uses Definitions:</th>
        <td>
            <code>marathon_repo_dir</code>
        </td>
    </tr>
</table>

Defines the environment and channel configuration for launching a `marathon` service locally, using the `sbt` utility from within the marathon project dir. 

**Important:** Using this configuration assumes you are running the tests within an environment with:
* A running zookeeper server
* Java & Scala installed

### `marathon-config-cluster-ext-ee.yml`

<table>
    <tr>
        <th>Uses Definitions:</th>
        <td>
            <code>cluster_url</code>
        </td>
    </tr>
</table>

Defines the environment and channel configuration for using marathon form an already deployed DC/OS Enterprise Cluster.

**Important:** This configuration will instruct the `dcos-perf-test-driver` to authenticate against the DC/OS cluster using the default credentials. This **will not work** with Open clusters.
