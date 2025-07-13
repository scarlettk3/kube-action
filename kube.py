C:\Users\nkdua\Downloads\actionupdateVS>kubectl exec -it k8s-error-agent-dev-6579b68854-gcm9b -- /bin/bash
root@k8s-error-agent-dev-6579b68854-gcm9b:/# cd /app
root@k8s-error-agent-dev-6579b68854-gcm9b:/app# python kube-action.py
success-8
2025-07-13 12:44:21,834 - k8s-error-agent-dev - INFO - Loaded in-cluster Kubernetes configuration
2025-07-13 12:44:21,840 - k8s-error-agent-dev - INFO - 

Starting Kubernetes Error Analysis Agent (with deployment watch and sequential failed pod analysis)


2025-07-13 12:44:21,848 - k8s-error-agent-dev - INFO - Starting Deployment watch for Helm install/upgrade/rollback events (strict pending logic)...
2025-07-13 12:44:21,849 - k8s-error-agent-dev - INFO - Reconciling pending ConfigMap with actual Helm state...
2025-07-13 12:44:22,214 - k8s-error-agent-dev - INFO - 
Found 4 namespaces in the cluster.

2025-07-13 12:44:22,214 - k8s-error-agent-dev - INFO - 
Checking for failed pods in namespace: default ...

2025-07-13 12:44:22,722 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace default

2025-07-13 12:44:22,723 - k8s-error-agent-dev - INFO - 
Checking for failed pods in namespace: kube-node-lease ...

2025-07-13 12:44:22,813 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-node-lease

2025-07-13 12:44:22,813 - k8s-error-agent-dev - INFO - 
Checking for failed pods in namespace: kube-public ...

2025-07-13 12:44:22,911 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-public

2025-07-13 12:44:22,912 - k8s-error-agent-dev - INFO - 
Checking for failed pods in namespace: kube-system ...

2025-07-13 12:44:23,931 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-system

2025-07-13 12:44:23,931 - k8s-error-agent-dev - INFO -
Waiting 60 seconds before next failed pod scan across all namespaces...
================================================================================

2025-07-13 12:44:27,433 - k8s-error-agent-dev - INFO - Checking for pending Helm revisions on startup...
2025-07-13 12:44:27,449 - k8s-error-agent-dev - INFO - Startup: Found pending revision 51 for nginx-1 in default, checking health for 30s...
2025-07-13 12:44:30,838 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=51, previous pending=51
2025-07-13 12:44:30,840 - k8s-error-agent-dev - INFO - Helm revision 51 for nginx-1 in default is not newer than pending 51, skipping.
2025-07-13 12:44:30,923 - k8s-error-agent-dev - INFO - Set pending revision 51 for release nginx-1 in default, starting health check for 30s.
2025-07-13 12:45:07,169 - k8s-error-agent-dev - INFO - Updated ConfigMap helm-stable-revisions with nginx-1: 51
2025-07-13 12:45:07,169 - k8s-error-agent-dev - INFO - Revision 51 for release nginx-1 in default is stable. Updated helm-stable-revisions.
2025-07-13 12:45:07,210 - k8s-error-agent-dev - INFO - Cleared pending revision for nginx-1 in default after health check.
2025-07-13 12:45:23,960 - k8s-error-agent-dev - INFO - 
Found 4 namespaces in the cluster.

2025-07-13 12:45:23,963 - k8s-error-agent-dev - INFO -
Checking for failed pods in namespace: default ...

2025-07-13 12:45:24,107 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace default

2025-07-13 12:45:24,113 - k8s-error-agent-dev - INFO -
Checking for failed pods in namespace: kube-node-lease ...

2025-07-13 12:45:24,228 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-node-lease

2025-07-13 12:45:24,229 - k8s-error-agent-dev - INFO -
Checking for failed pods in namespace: kube-public ...

2025-07-13 12:45:24,235 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-public

2025-07-13 12:45:24,235 - k8s-error-agent-dev - INFO -
Checking for failed pods in namespace: kube-system ...

2025-07-13 12:45:24,442 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-system

2025-07-13 12:45:24,442 - k8s-error-agent-dev - INFO -
Waiting 60 seconds before next failed pod scan across all namespaces...
================================================================================

2025-07-13 12:46:16,391 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=52, previous pending=45
2025-07-13 12:46:16,391 - k8s-error-agent-dev - INFO - Starting health check for Helm revision 52 for release nginx-1 in default
2025-07-13 12:46:25,600 - k8s-error-agent-dev - INFO - 
Found 4 namespaces in the cluster.

2025-07-13 12:46:26,181 - k8s-error-agent-dev - INFO - 
Checking for failed pods in namespace: default ...

2025-07-13 12:46:27,984 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace default

2025-07-13 12:46:27,992 - k8s-error-agent-dev - INFO -
Checking for failed pods in namespace: kube-node-lease ...

2025-07-13 12:46:28,093 - k8s-error-agent-dev - INFO - Set pending revision 52 for release nginx-1 in default, starting health check for 30s.
2025-07-13 12:46:28,492 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-node-lease

2025-07-13 12:46:28,492 - k8s-error-agent-dev - INFO -
Checking for failed pods in namespace: kube-public ...

2025-07-13 12:46:28,496 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=52, previous pending=52
2025-07-13 12:46:28,497 - k8s-error-agent-dev - INFO - Helm revision 52 for nginx-1 in default is not newer than pending 52, skipping.
2025-07-13 12:46:28,582 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-public

2025-07-13 12:46:28,588 - k8s-error-agent-dev - INFO - 
Checking for failed pods in namespace: kube-system ...

2025-07-13 12:46:29,183 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-system

2025-07-13 12:46:29,184 - k8s-error-agent-dev - INFO - 
Waiting 60 seconds before next failed pod scan across all namespaces...
================================================================================

2025-07-13 12:46:30,404 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=52, previous pending=52
2025-07-13 12:46:30,404 - k8s-error-agent-dev - INFO - Helm revision 52 for nginx-1 in default is not newer than pending 52, skipping.
2025-07-13 12:46:31,892 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=52, previous pending=52
2025-07-13 12:46:31,893 - k8s-error-agent-dev - INFO - Helm revision 52 for nginx-1 in default is not newer than pending 52, skipping.
2025-07-13 12:46:33,283 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=52, previous pending=52
2025-07-13 12:46:33,284 - k8s-error-agent-dev - INFO - Helm revision 52 for nginx-1 in default is not newer than pending 52, skipping.
2025-07-13 12:46:34,982 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=52, previous pending=52
2025-07-13 12:46:34,982 - k8s-error-agent-dev - INFO - Helm revision 52 for nginx-1 in default is not newer than pending 52, skipping.
2025-07-13 12:46:45,994 - k8s-error-agent-dev - WARNING - Could not fetch Helm revision for release nginx-1 in default
2025-07-13 12:46:51,515 - k8s-error-agent-dev - INFO - Detected newer Helm revision 53 for nginx-1 in default during health check, aborting and starting new check.
2025-07-13 12:46:54,495 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=53, previous pending=46
2025-07-13 12:46:54,497 - k8s-error-agent-dev - INFO - Starting health check for Helm revision 53 for release nginx-1 in default
2025-07-13 12:46:59,977 - k8s-error-agent-dev - INFO - Set pending revision 53 for release nginx-1 in default, starting health check for 30s.
2025-07-13 12:47:01,681 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=53, previous pending=53
2025-07-13 12:47:01,683 - k8s-error-agent-dev - INFO - Helm revision 53 for nginx-1 in default is not newer than pending 53, skipping.
2025-07-13 12:47:16,186 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=53, previous pending=46
2025-07-13 12:47:16,277 - k8s-error-agent-dev - INFO - Starting health check for Helm revision 53 for release nginx-1 in default
2025-07-13 12:47:22,987 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-2, ns=default, detected Helm revision=1, previous pending=1
2025-07-13 12:47:22,988 - k8s-error-agent-dev - INFO - Helm revision 1 for nginx-2 in default is not newer than pending 1, skipping.
2025-07-13 12:47:25,883 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-2, ns=default, detected Helm revision=1, previous pending=1
2025-07-13 12:47:25,891 - k8s-error-agent-dev - INFO - Helm revision 1 for nginx-2 in default is not newer than pending 1, skipping.
2025-07-13 12:47:28,482 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-2, ns=default, detected Helm revision=1, previous pending=1
2025-07-13 12:47:28,482 - k8s-error-agent-dev - INFO - Helm revision 1 for nginx-2 in default is not newer than pending 1, skipping.
2025-07-13 12:47:29,290 - k8s-error-agent-dev - INFO - 
Found 4 namespaces in the cluster.

2025-07-13 12:47:29,290 - k8s-error-agent-dev - INFO -
Checking for failed pods in namespace: default ...

2025-07-13 12:47:31,478 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace default

2025-07-13 12:47:31,479 - k8s-error-agent-dev - INFO - 
Checking for failed pods in namespace: kube-node-lease ...

2025-07-13 12:47:31,573 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-node-lease

2025-07-13 12:47:31,573 - k8s-error-agent-dev - INFO -
Checking for failed pods in namespace: kube-public ...

2025-07-13 12:47:31,580 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-public

2025-07-13 12:47:31,581 - k8s-error-agent-dev - INFO - 
Checking for failed pods in namespace: kube-system ...

2025-07-13 12:47:32,778 - k8s-error-agent-dev - INFO - Found 0 failed pods in namespace kube-system

2025-07-13 12:47:32,779 - k8s-error-agent-dev - INFO -
Waiting 60 seconds before next failed pod scan across all namespaces...
================================================================================

2025-07-13 12:47:33,680 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-2, ns=default, detected Helm revision=1, previous pending=1
2025-07-13 12:47:33,680 - k8s-error-agent-dev - INFO - Helm revision 1 for nginx-2 in default is not newer than pending 1, skipping.
2025-07-13 12:47:35,775 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=53, previous pending=53
2025-07-13 12:47:35,776 - k8s-error-agent-dev - INFO - Helm revision 53 for nginx-1 in default is not newer than pending 53, skipping.
2025-07-13 12:47:39,279 - k8s-error-agent-dev - INFO - Deployment event: release=nginx-1, ns=default, detected Helm revision=53, previous pending=53
2025-07-13 12:47:39,280 - k8s-error-agent-dev - INFO - Helm revision 53 for nginx-1 in default is not newer than pending 53, skipping.


C:\Users\nkdua\Downloads\actionupdateVS>helm history nginx-1                                                                     
REVISION        UPDATED                         STATUS          CHART           APP VERSION     DESCRIPTION                      
44              Sun Jul 13 08:24:20 2025        superseded      nginx-13.2.24   1.23.3          Rollback to 40
45              Sun Jul 13 16:30:25 2025        superseded      nginx-21.0.1    1.29.0          Rollback to 36
46              Sun Jul 13 11:01:07 2025        superseded      nginx-13.2.24   1.23.3          Rollback to 44
47              Sun Jul 13 16:54:33 2025        superseded      nginx-21.0.1    1.29.0          Rollback to 43
48              Sun Jul 13 11:25:38 2025        superseded      nginx-13.2.24   1.23.3          Rollback to 46
49              Sun Jul 13 17:46:38 2025        superseded      nginx-21.0.1    1.29.0          Upgrade complete
50              Sun Jul 13 12:17:39 2025        superseded      nginx-13.2.24   1.23.3          Rollback to 46
51              Sun Jul 13 12:17:48 2025        superseded      nginx-13.2.24   1.23.3          Rollback to 46
52              Sun Jul 13 18:16:04 2025        superseded      nginx-21.0.1    1.29.0          Upgrade complete
53              Sun Jul 13 12:46:38 2025        deployed        nginx-13.2.24   1.23.3          Rollback to 51

C:\Users\nkdua\Downloads\actionupdateVS>
