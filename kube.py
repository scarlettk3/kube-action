if there is a new helm release or an upgrade, even after the rollback there will be a helm upgrade revision right,
they should be kept in pending for 30s health check if they are stable the update the stable cm

ok the current code isnt doing that,

it is still keeping the old revision in pending cm for health check

let me tell you how it should work:

any install/upgrade keep in pending cm , check the pod for 30s,
a. if healthy, update the stable cm with that revision which was in pending and remove that from pending cm or keep it "" empty as it is marked,
b. if the revision not healthy after 30s, then just keep the pending cm "" empty i.e remove the revision from pending cm and no need to update stable cm as the pods are not healthy for that revision

while the pending cm's revision is in health check 30s or pending revision "", if the same helm release got upgraded, stop the current revision and update the pending cm to the latest upgrade no matter how many before are there, then do the step 1 for it.

when a pod fails, if the remediation is rollback, then that revision should also be kept in pending and follow the step1.

there might be some case where the first helm revision 1 can give error, there will be no previous chart to rollback, as the pods will not be healthy it should follow step1.b.
what i meant to say is no matter what it should only update the stable cm when the revision 30s pod check health is healthy, it should not update if it they are not healthy, if so it can give error,
the pod healthyness is utmost important to mark the revision as healthy, so after 30 s if healthy onlythey should update else no.

what i want is like only the latest upgrade or install should be in pending, like pending should be either current deployment which is in processing or "" after it found the revison healthy or not irrespective of that.
