## kubernetes AI Agent
---------------------
This project provides an advanced Kubernetes agent that uses Large Language Model (LLM) analysis (via Mistral) to diagnose and remediate failed pods in your cluster. 
It is designed for robust, safe, and auditable remediation, with a focus on Helm-managed workloads.

#### **Key Features**:

1. **_LLM-Driven Remediation_**: Uses Mistral LLM to analyze failed pods and recommend only safe, explicit actions (RESTART_POD or HELM_ROLLBACK). No automatic rollback or pod deletion unless the LLM recommends it.
2. **_Sequential and Robust Pod Analysis_**: Failed pods are processed one at a time, ensuring careful, auditable remediation.
3. **_Stable Revision Tracking_**: After a successful Helm deployment or upgrade, the agent marks the revision as stable in a ConfigMap. This enables safe rollbacks to known-good states.

**_Separation of Concerns via Parallel Processes_**:
_Process 1_: Continuously checks for failed pods and, if the LLM recommends, performs a rollback to the last stable revision recorded in the ConfigMap. This process does not wait for new revisions to be marked as stable.<br>
_Process 2_: Monitors Helm install/upgrade events. After each deployment, it waits (e.g., 30 seconds) to verify pod health. If the deployment is stable, it updates the ConfigMap with the new stable revision.
This process ensures only healthy revisions are marked as stable, independent of the remediation process.

