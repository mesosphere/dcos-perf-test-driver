# Postgres SQL Schema

This document explains the table schema the `PostgRESTReporter` reporter is expected to which to report the data.

## Terminology

* **job** : A scale test job
* **run** : A repeating scale test sampling process in order to collect statistics. One or more _runs_ are executed within a single _job_.
* **test** : A scale test that is executed during a _run_
* **phase** : A checkpoint during the execution of a _test_ during which a new set of _parameters_ is given to the application and a new sampling process begins.
* **parameter** : An input value to the _test_. For example `instances=10`.
* **mmetric** : An output value from the _test_. For example `deployTime=1.42s`

## Tables

### `*_job` Job Indexing Table

This table keeps track of the high-level job structure. Since more than one project will be using the same database, the `project` field should be populated with the name of the project that started this job.

<table>
    <tr>
        <th><u>jid</u></th>
        <th>started</th>
        <th>completed</th>
        <th>status</th>
        <th>project</th>
    </tr>
    <tr>
        <td>Job UUID</td>
        <td>Started Timestamp</td>
        <td>Finished Timestamp</td>
        <td>Job Status</td>
        <td>Project Name</td>
    </tr>
</table>

#### DDL

```sql
CREATE TABLE metric_data.perf_test_job
(
    jid uuid NOT NULL,
    started timestamp without time zone NOT NULL,
    completed timestamp without time zone NOT NULL,
    status integer NOT NULL,
    project character varying(128) NOT NULL,
    PRIMARY KEY (jid)
)
WITH (
    OIDS = FALSE
);

ALTER TABLE metric_data.perf_test_job
    OWNER to postgrest;
```

### `*_job_meta` Job Metadata

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
        <td>Run UUID</td>
        <td>Name</td>
        <td>Value</td>
    </tr>
</table>

#### DDL

```sql
CREATE TABLE metric_data.perf_test_job_meta
(
    id serial NOT NULL,
    jid uuid NOT NULL,
    name character varying(32) NOT NULL,
    value character varying(128) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT jid FOREIGN KEY (jid)
        REFERENCES metric_data.perf_test_job (jid) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
)
WITH (
    OIDS = FALSE
);

ALTER TABLE metric_data.perf_test_job_meta
    OWNER to postgrest;
```

### `*_job_phases` Job Phases

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
        <td>Phase UUID</td>
        <td>Job UUID</td>
        <td><strike>Run Index</strike></td>
        <td><strike>Timestamp</strike></td>
    </tr>
</table>

#### DDL

```sql
CREATE TABLE metric_data.perf_test_job_phases
(
    pid uuid NOT NULL,
    jid uuid NOT NULL,
    run integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    PRIMARY KEY (pid),
    CONSTRAINT jid FOREIGN KEY (jid)
        REFERENCES metric_data.perf_test_job (jid) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
)
WITH (
    OIDS = FALSE
);

ALTER TABLE metric_data.perf_test_job_phases
    OWNER to postgresql;
```

### `*_lookup_metrics` Metric lookup table

Since a metric might be renamed or changed over time, we are using UUIDs to refer to metrics. This table contains the lookup information between the UUID and the metric name.

<table>
    <tr>
        <th><u>metric</u></th>
        <th>name</th>
        <th>title</th>
        <th>units</th>
    </tr>
    <tr>
        <td>Metric UUID</td>
        <td>Name</td>
        <td>Axis Title</td>
        <td>Units</td>
    </tr>
</table>

```sql
CREATE TABLE metric_data.perf_test_lookup_metrics
(
    metric uuid NOT NULL,
    name character varying(32) NOT NULL,
    title character varying(128) NOT NULL,
    units character varying(16),
    PRIMARY KEY (metric)
)
WITH (
    OIDS = FALSE
);

ALTER TABLE metric_data.perf_test_lookup_metrics
    OWNER to postgrest;
```

### `*_lookup_parameters` Parameter lookup table

Like the _lookup metrics_ table, this table contains the lookup information between the UUID and the parameter name.

<table>
    <tr>
        <th><u>parameter</u></th>
        <th>name</th>
        <th>title</th>
        <th>units</th>
    </tr>
    <tr>
        <td>Parameter UUID</td>
        <td>Name</td>
        <td>Title</td>
        <td>Units</td>
    </tr>
</table>

```sql
CREATE TABLE metric_data.perf_test_lookup_parameters
(
    parameter uuid NOT NULL,
    name character varying(32) NOT NULL,
    title character varying(128) NOT NULL,
    units character varying(16),
    PRIMARY KEY (parameter)
)
WITH (
    OIDS = FALSE
);

ALTER TABLE metric_data.perf_test_lookup_parameters
    OWNER to postgrest;
```

### `*_phase_flags` Phase Flags

During each _phase_ one or more status _flags_ might be raised, indicating internal failures or other status information. These flags are submitted when the phase is completed and it's useful to collect them.

<table>
    <tr>
        <th><u>id</u></th>
        <th>pid</th>
        <th>name</th>
        <th>value</th>
    </tr>
    <tr>
        <td>Index</td>
        <td>Phase UUID</td>
        <td>Name</td>
        <td>Value</td>
    </tr>
</table>

```sql
CREATE TABLE metric_data.perf_test_phase_flags
(
    id serial NOT NULL,
    pid uuid NOT NULL,
    name character varying(32) NOT NULL,
    value character varying(128) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT pid FOREIGN KEY (pid)
        REFERENCES metric_data.perf_test_job_phases (pid) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
)
WITH (
    OIDS = FALSE
);

ALTER TABLE metric_data.perf_test_phase_flags
    OWNER to postgrest;
```

### `*_phase_params` Phase Parameters

During each _phase_ the _test_ is given some _parameters_. These _parameters_ are usually the plot axis that we are interested in. (ex. `instances`)

<table>
    <tr>
        <th><u>id</u></th>
        <th>pid<th>
        <th>parameter</th>
        <th>value</th>
    </tr>
    <tr>
        <td>Index</td>
        <td>Phase ID</td>
        <td>Parameter UUID</td>
        <td>Parameter value</td>
    </tr>
</table>

#### DDL

```sql
CREATE TABLE metric_data.perf_test_phase_params
(
    id serial NOT NULL,
    pid uuid NOT NULL,
    parameter uuid NOT NULL,
    value character varying(128) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT pid FOREIGN KEY (pid)
        REFERENCES metric_data.perf_test_job_phases (pid) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT parameter FOREIGN KEY (parameter)
        REFERENCES metric_data.perf_test_lookup_parameters (parameter) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
)
WITH (
    OIDS = FALSE
);

ALTER TABLE metric_data.perf_test_phase_flags
    OWNER to postgrest;
```

### `*_phase_metrics` Phase Metrics

During the _test_ various _metrics_ are extracted and emmited the moment their sampling is completed. These metrics are effectively the results of the test.

<table>
    <tr>
        <th><u>id</u></th>
        <th>pid</th>
        <th>metric</th>
        <th>value</th>
        <th>timestamp</th>
    </tr>
    <tr>
        <td>Index</td>
        <td>Phase UUID</td>
        <td>Metric UUID</td>
        <td>Value</td>
        <td>Timestamp</td>
    </tr>
</table>

#### DDL

```sql
CREATE TABLE metric_data.perf_test_phase_metrics
(
    id serial NOT NULL,
    pid uuid NOT NULL,
    metric uuid NOT NULL,
    value numeric NOT NULL,
    timestamp timestamp without time zone NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT pid FOREIGN KEY (pid)
        REFERENCES metric_data.perf_test_job_phases (pid) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT metric FOREIGN KEY (metric)
        REFERENCES metric_data.perf_test_lookup_metrics (metric) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
)
WITH (
    OIDS = FALSE
);

ALTER TABLE metric_data.perf_test_phase_flags
    OWNER to postgrest;
```

## Querying

The following query can be used to fetch a 1D plot for jobs that have only 1 axis on it's parameters:

```sql
SELECT
    "metric_data"."perf_test_job_phases".jid,
    "metric_data"."perf_test_phase_params"."value" AS "x",
    "metric_data"."perf_test_phase_metrics"."value" AS "y"

FROM
    "metric_data"."perf_test_phase_params"
    JOIN "metric_data"."perf_test_phase_metrics"
        ON "metric_data"."perf_test_phase_params".pid = 
           "metric_data"."perf_test_phase_metrics".pid
    JOIN "metric_data"."perf_test_job_phases"
        ON "metric_data"."perf_test_phase_params".pid = 
           "metric_data"."perf_test_job_phases".pid
WHERE
    -- The axis you want to view (assuming only 1 dimention)
    "metric_data"."perf_test_phase_params"."parameter" = 
        '4a003e85-e8bb-4a95-a340-eec1727cfd0d' AND

    -- The metric you want to plot
    "metric_data"."perf_test_phase_metrics"."metric" = 
        'cfac77fc-eb24-4862-aedd-89066441c416' AND

    -- Job selection based on it's metadata.
    -- In this example we are selecting the latest `master` version.
    "metric_data"."perf_test_job_phases".jid IN (
        SELECT
            "metric_data"."perf_test_job_meta".jid
        FROM
            "metric_data"."perf_test_job_meta"
        WHERE
            "metric_data"."perf_test_job_meta"."name" = 'version' AND
            "metric_data"."perf_test_job_meta"."value" = 'master'
        ORDER BY
            "metric_data"."perf_test_job_meta".id DESC
        LIMIT 1
    )
```

