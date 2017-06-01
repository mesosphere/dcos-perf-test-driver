# Test Fragments

This directory contains the test policy configurations for driving the scale tests. They are agnostic of the rest of the configuration they only define the policies that emit the parameter updates.

## Files

<table>
    <tr>
        <th>Filename</th>
        <th>Policy</th>
        <th>Description</th>
    </tr>
    <tr>
        <th>1-app-n-instances-seq.yml</th>
        <td><code>ChainedDeploymentPolicy</code></td>
        <td>Scale <code>instances</code> parameter from 1 to 131072 at logarithmic intervals of power of two. This policy will wait until a `MarathonDeploymentSuccess` event is received before moving to the next instance.</td>
    </tr>
    <tr>
        <th>1-instance-n-apps-seq.yml</th>
        <td><code>BulkChainedDeploymentPolicy</code></td>
        <td>Scale <code>apps</code> parameter from 1 to 131072 at logarithmic intervals of power of two. This policy will wait until a number of `MarathonDeploymentSuccess` events is received before moving to the next instance.</td>
    </tr>
</table>

## Requires
