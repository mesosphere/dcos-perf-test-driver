
# Terminology

* **job** : A scale test job
* **run** : A repeating scale test sampling process in order to collect statistics. One or more _runs_ are executed within a single _job_.
* **test** : A scale test that is executed during a _run_
* **phase** : A checkpoint during the execution of a _test_ during which a new set of _parameters_ is given to the application and a new sampling process begins.
* **parameter** : An input value to the _test_. For example `instances=10`.
* **mmetric** : An output value from the _test_. For example `deployTime=1.42s`

# Tables

## `*_job` Job Indexing Table

This table keeps track of the high-level job structure

<table>
    <tr>
        <th><u>jid</u></th>
        <th>started</th>
        <th>finished</th>
        <th>status</th>
    </tr>
    <tr>
        <td>Job ID</td>
        <th>Started Timestamp</th>
        <th>Finished Timestamp</th>
        <th>Job Status</th>
    </tr>
</table>

## `*_job_meta` Job Metadata

Each job has a set of metadata that can be used to identify the process being executed. For example `environment`, `version`, `git_hash` etc.

They are unique for every run, therefore they are groupped with the run ID.

<table>
    <tr>
        <th><u>id</u></th>
        <th>jid</th>
        <th>name</th>
        <th>value</th>
    </tr>
    <tr>
        <td>Index</td>
        <td>Run ID</td>
        <td>Name</td>
        <td>Value</td>
    </tr>
</table>

## `*_job_phases` Job Phases

Eventually the test will go through various _phases_ that are repeated during every _run_. Since the _phase_ is groupping various parameter/metric combinations, we are using the `job_phases` table to index them.

_(This table could actually be merged into the `phase_` tables below)_

<table>
    <tr>
        <th><u>pid</u></th>
        <th>jid</th>
        <th>run</th>
        <th>timestamp</th>
    </tr>
    <tr>
        <td>Phase ID</td>
        <td>Job ID</td>
        <td>Run Index</td>
        <td>Timestamp</td>
    </tr>
</table>

## `*_phase_flags` Job Flags

During each _phase_ one or more status _flags_ might be raised, indicating internal failures or other status information. These flags are submitted when the phase is completed and it's useful to collect them.

<table>
    <tr>
        <th><u>pid</u></th>
        <th>jid</th>
        <th>run</th>
        <th>timestamp</th>
    </tr>
    <tr>
        <td>Phase ID</td>
        <td>Job ID</td>
        <td>Run Index</td>
        <td>Timestamp</td>
    </tr>
</table>

## `*_phase_params` Phase Parameters

During each _phase_ the _test_ is given some _parameters_. These _parameters_ are usually the plot axis that we are interested in. (ex. `instances`)

<table>
    <tr>
        <th><u>pid</u></th>
        <th>name</th>
        <th>value</th>
    </tr>
    <tr>
        <td>Phase ID</td>
        <td>Parameter name</td>
        <td>Parameter value</td>
    </tr>
</table>

## `*_phase_metrics` Phase Metrics

During the _test_ various _metrics_ are extracted and emmited the moment their sampling is completed. These metrics are effectively the results of the test.

<table>
    <tr>
        <th><u>pid</u></th>
        <th>name</th>
        <th>value</th>
        <th>timestamp</th>
    </tr>
    <tr>
        <td>Phase ID</td>
        <td>Metric name</td>
        <td>Metric value</td>
        <td>Sample Timestamp</td>
    </tr>
</table>

# PostgREST requests

When the job is completed, the reporter will do the following:

1. Allocate a new job record and get back the `jid`

    ```js
    POST /job HTTP/1.1
    
    { "started": 1234.12, "finished": 1234.412, "status": 0 }
    ```

2. Bulk-submit the job metadata

    ```js
    POST /job_meta HTTP/1.1

    [
        { "jid": 123, "name": "..", "value": "..." }
    ]
    ```

2. Bulk-submit the phases

    ```js
    POST /job_phases HTTP/1.1

    [
        { "jid": 123, "name": "..", "value": "..." }
    ]
    ```




