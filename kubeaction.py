#!/usr/bin/env python3
import os
import time
import json
import logging
import datetime
import requests
from kubernetes import client, config, watch
import concurrent.futures
import traceback
import queue
import threading
import re
import subprocess
from typing import Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,  # Logging level set to INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Ensures logs go to stdout for kubectl logs
        logging.FileHandler('/app/output/k8s_error_agent.log')  # Optional file logging
    ]
)
logger = logging.getLogger("k8s-error-agent-dev")

# Configuration settings
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/output")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "60"))  # In seconds
MAX_CONCURRENT_REQUESTS = 2  # Limit concurrent AI analysis requests
REQUEST_DELAY = 5  # Seconds between requests to avoid rate limiting

# Auto-remediation settings
AUTO_REMEDIATION_ENABLED = os.environ.get("AUTO_REMEDIATION_ENABLED", "false").lower() == "true"
DRY_RUN_MODE = os.environ.get("DRY_RUN_MODE", "false").lower() == "true"  # Default to dry run for safety


# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def sanitize_text(text, max_length=2000):
    """Sanitize and truncate text to prevent oversized requests"""
    if text is None:
        return ""
    try:
        # Sanitize and truncate
        sanitized = text.encode("utf-8", errors="replace").decode("utf-8")
        return sanitized[:max_length]
    except Exception as e:
        logger.error(f"Error sanitizing text: {e}")
        return str(text)[:max_length]

class K8sErrorAnalysisAgent:
    def get_all_helm_releases(self):
        """Return a list of (namespace, release_name, revision) for all Helm releases in all namespaces."""
        releases = []
        try:
            # Get all namespaces
            namespaces = self.get_all_namespaces()
            for ns in namespaces:
                cmd = f"helm list -n {ns} --output json"
                result = subprocess.run(cmd.split(), capture_output=True, text=True)
                if result.returncode != 0:
                    continue
                for rel in json.loads(result.stdout):
                    name = rel.get("name")
                    revision = str(rel.get("revision"))
                    if name and revision:
                        releases.append((ns, name, revision))
        except Exception as e:
            logger.error(f"Error getting all Helm releases: {e}")
        return releases

    def get_pending_revision_from_configmap(self, namespace, release_name):
        """Get the pending revision for a release from ConfigMap."""
        configmap_name = "helm-pending-revisions"
        key = f"{namespace}__{release_name}-pending-revision"
        try:
            cm = self.v1.read_namespaced_config_map(configmap_name, "default")
            if cm.data and key in cm.data:
                return cm.data[key]
        except client.exceptions.ApiException as e:
            if e.status == 404:
                return None
            logger.error(f"Error reading pending revision ConfigMap: {e}")
        except Exception as e:
            logger.error(f"Error reading pending revision ConfigMap: {e}")
        return None

    def set_pending_revision_in_configmap(self, namespace, release_name, revision):
        """Set the pending revision for a release in the ConfigMap (overwrites any previous)."""
        configmap_name = "helm-pending-revisions"
        key = f"{namespace}__{release_name}-pending-revision"
        try:
            # Try to patch if exists, else create
            try:
                cm = self.v1.read_namespaced_config_map(configmap_name, "default")
                data = cm.data or {}
                data[key] = revision
                body = {"data": data}
                self.v1.patch_namespaced_config_map(configmap_name, "default", body)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    # Create new ConfigMap
                    data = {key: revision}
                    cm = client.V1ConfigMap(metadata=client.V1ObjectMeta(name=configmap_name), data=data)
                    self.v1.create_namespaced_config_map("default", cm)
                else:
                    raise
        except Exception as e:
            logger.error(f"Error setting pending revision in ConfigMap: {e}")

    def clear_pending_revision_in_configmap(self, namespace, release_name):
        """Set the pending revision for a release in the ConfigMap to empty string ("")."""
        configmap_name = "helm-pending-revisions"
        key = f"{namespace}__{release_name}-pending-revision"
        try:
            cm = self.v1.read_namespaced_config_map(configmap_name, "default")
            data = cm.data or {}
            data[key] = ""
            body = {"data": data}
            self.v1.patch_namespaced_config_map(configmap_name, "default", body)
        except client.exceptions.ApiException as e:
            if e.status != 404:
                logger.error(f"Error clearing pending revision in ConfigMap: {e}")
        except Exception as e:
            logger.error(f"Error clearing pending revision in ConfigMap: {e}")

    def process_pending_revisions_on_startup(self):
        """On startup, check for any pending revisions in the ConfigMap and process them for 30s health check."""
        logger.info("Checking for pending Helm revisions on startup...")
        configmap_name = "helm-pending-revisions"
        try:
            cm = self.v1.read_namespaced_config_map(configmap_name, "default")
            data = cm.data or {}
            for key, revision in data.items():
                if key.endswith("-pending-revision") and revision:
                    try:
                        ns, release = key[:-len("-pending-revision")].split("__", 1)
                        logger.info(f"Startup: Found pending revision {revision} for {release} in {ns}, checking health...")
                        threading.Thread(target=self.handle_helm_post_install_or_upgrade, args=(ns, release, 30), kwargs={"revision": revision}, daemon=True).start()
                    except Exception as e:
                        logger.error(f"Error processing pending revision {revision} for {key}: {e}")
        except client.exceptions.ApiException as e:
            if e.status != 404:
                logger.error(f"Error reading pending revision ConfigMap: {e}")
        except Exception as e:
            logger.error(f"Error reading pending revision ConfigMap: {e}")

    def reconcile_pending_configmap_with_helm(self):
        """
        On startup, ensure pending ConfigMap matches actual Helm state for all releases.
        """
        logger.info("Reconciling pending ConfigMap with actual Helm state...")
        releases = self.get_all_helm_releases()
        for ns, release_name, helm_revision in releases:
            pending = self.get_pending_revision_from_configmap(ns, release_name)
            if pending != helm_revision:
                logger.info(f"Updating pending revision for {release_name} in {ns} to latest Helm revision {helm_revision}")
                self.set_pending_revision_in_configmap(ns, release_name, helm_revision)

    def _configmap_exists(self, name, namespace):
        try:
            self.v1.read_namespaced_config_map(name, namespace)
            return True
        except client.exceptions.ApiException as e:
            if e.status == 404:
                return False
            raise
        except Exception:
            return False
    def __init__(self):
        try:
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except config.ConfigException:
            config.load_kube_config()
            logger.info("Loaded local Kubernetes configuration")

        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.already_analyzed_pods = set()
        self.helm_releases = {}
        self.helm_rollback_attempts = {}
        self.failed_pod_queue = queue.Queue()
        self.agent_active_event = threading.Event()  # To control agent active state

    def get_all_namespaces(self):
        """Get all namespaces in the cluster"""
        namespaces = self.v1.list_namespace()
        return [ns.metadata.name for ns in namespaces.items]

    def get_failed_pods(self, namespace):
        """Get all pods with non-successful status in a specific namespace, including failed init containers"""
        pods = self.v1.list_namespaced_pod(namespace=namespace)
        failed_pods = []

        for pod in pods.items:
            pod_status = pod.status.phase
            container_statuses = pod.status.container_statuses if pod.status.container_statuses else []
            init_container_statuses = pod.status.init_container_statuses if hasattr(pod.status, 'init_container_statuses') and pod.status.init_container_statuses else []

            # Check if pod is in a failed/error state (main or init containers)
            failed = False
            if pod_status in ["Failed", "Unknown"]:
                failed = True
            if any(cs.state.waiting and cs.state.waiting.reason in ["CrashLoopBackOff", "Error", "ErrImagePull", "ImagePullBackOff"]
                   for cs in container_statuses):
                failed = True
            if any(cs.state.terminated and cs.state.terminated.exit_code != 0
                   for cs in container_statuses):
                failed = True
            # Check init containers for failure reasons
            if any(cs.state.waiting and cs.state.waiting.reason in ["CrashLoopBackOff", "Error", "ErrImagePull", "ImagePullBackOff"]
                   for cs in init_container_statuses):
                failed = True
            if any(cs.state.terminated and cs.state.terminated.exit_code != 0
                   for cs in init_container_statuses):
                failed = True

            pod_key = f"{namespace}/{pod.metadata.uid}"
            if failed and pod_key not in self.already_analyzed_pods:
                logger.info(f"Found failed pod: {pod_key}")
                failed_pods.append(pod)

        return failed_pods

    def get_pod_logs(self, pod, namespace):
        """Get logs from all containers in a pod"""
        logs = {}

        try:
            # If the pod has containers, get logs for each one
            if pod.spec.containers:
                for container in pod.spec.containers:
                    try:
                        container_log = self.v1.read_namespaced_pod_log(
                            name=pod.metadata.name,
                            namespace=namespace,
                            container=container.name,
                            tail_lines=50  # Reduced from 100 to limit payload size
                        )
                        logs[container.name] = sanitize_text(container_log)
                    except Exception as e:
                        logs[container.name] = f"Error retrieving logs: {str(e)}"

            # Also get pod events which can be helpful for debugging
            field_selector = f"involvedObject.name={pod.metadata.name}"
            events = self.v1.list_namespaced_event(
                namespace=namespace,
                field_selector=field_selector
            )
            events_text = "\n".join([
                f"{event.last_timestamp}: {event.reason} - {event.message}"
                for event in events.items
            ])
            logs["events"] = sanitize_text(events_text)

        except Exception as e:
            logger.error(f"Error getting logs for pod {pod.metadata.name}: {str(e)}")
            logs["error"] = str(e)

        return logs
    def get_node_resources(self, node_name):
        """Get node resource information to understand capacity constraints"""
        try:
            node = self.v1.read_node(node_name)
            allocatable = node.status.allocatable
            capacity = node.status.capacity

            return {
                "allocatable": dict(allocatable) if allocatable else {},
                "capacity": dict(capacity) if capacity else {},
                "conditions": [
                    {
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason or ""
                    }
                    for condition in (node.status.conditions or [])
                ]
            }
        except Exception as e:
            logger.error(f"Error getting node resources for {node_name}: {e}")
            return {}

    def get_namespace_resource_quotas(self, namespace):
        """Get resource quotas for the namespace"""
        try:
            quotas = self.v1.list_namespaced_resource_quota(namespace)
            return [
                {
                    "name": quota.metadata.name,
                    "hard": dict(quota.spec.hard) if quota.spec.hard else {},
                    "used": dict(quota.status.used) if quota.status and quota.status.used else {}
                }
                for quota in quotas.items
            ]
        except Exception as e:
            logger.error(f"Error getting resource quotas for namespace {namespace}: {e}")
            return []

    def get_related_pods_status(self, namespace, pod):
        """Get status of related pods (same deployment/replicaset) for pattern analysis"""
        try:
            related_pods = []
            pod_labels = pod.metadata.labels or {}

            # Find pods with similar labels (same app, deployment, etc.)
            if 'app' in pod_labels or 'app.kubernetes.io/name' in pod_labels:
                app_name = pod_labels.get('app') or pod_labels.get('app.kubernetes.io/name')
                selector = f"app={app_name}" if 'app' in pod_labels else f"app.kubernetes.io/name={app_name}"

                pods = self.v1.list_namespaced_pod(namespace, label_selector=selector)

                for related_pod in pods.items:
                    if related_pod.metadata.name != pod.metadata.name:
                        related_pods.append({
                            "name": related_pod.metadata.name,
                            "phase": related_pod.status.phase,
                            "ready": all(cs.ready for cs in (related_pod.status.container_statuses or [])),
                            "restart_count": sum(cs.restart_count for cs in (related_pod.status.container_statuses or []))
                        })

            return related_pods
        except Exception as e:
            logger.error(f"Error getting related pods: {e}")
            return []

    def get_recent_deployment_history(self, namespace, pod):
        """Get recent deployment history to understand if this is a new deployment issue"""
        try:
            # Try to find the deployment that owns this pod
            owner_refs = pod.metadata.owner_references or []
            for owner in owner_refs:
                if owner.kind == "ReplicaSet":
                    # Get the ReplicaSet
                    rs = self.apps_v1.read_namespaced_replica_set(owner.name, namespace)
                    rs_owners = rs.metadata.owner_references or []

                    for rs_owner in rs_owners:
                        if rs_owner.kind == "Deployment":
                            # Get deployment rollout history
                            deployment = self.apps_v1.read_namespaced_deployment(rs_owner.name, namespace)

                            # Get recent replica sets for this deployment
                            rs_list = self.apps_v1.list_namespaced_replica_set(
                                namespace, 
                                label_selector=f"app={deployment.metadata.labels.get('app', '')}"
                            )

                            recent_rs = []
                            for rs in rs_list.items:
                                if rs.metadata.creation_timestamp:
                                    recent_rs.append({
                                        "name": rs.metadata.name,
                                        "replicas": rs.spec.replicas,
                                        "ready_replicas": rs.status.ready_replicas or 0,
                                        "creation_time": rs.metadata.creation_timestamp,
                                        "revision": rs.metadata.annotations.get("deployment.kubernetes.io/revision", "unknown")
                                    })

                            # Sort by creation time, get last 3
                            recent_rs.sort(key=lambda x: x["creation_time"], reverse=True)
                            return recent_rs[:3]

            return []
        except Exception as e:
            logger.error(f"Error getting deployment history: {e}")
            return []

    def check_image_availability(self, image_name):
        """Check if an image pull issue might be due to image availability"""
        try:
            # This is a simplified check - in production you might want to
            # actually attempt a docker pull or check registry APIs
            common_registries = ["docker.io", "gcr.io", "quay.io", "registry.k8s.io"]

            image_info = {
                "image": image_name,
                "registry": "unknown",
                "likely_public": False
            }

            for registry in common_registries:
                if registry in image_name:
                    image_info["registry"] = registry
                    image_info["likely_public"] = True
                    break
                
            return image_info
        except Exception as e:
            logger.error(f"Error checking image availability: {e}")
            return {"image": image_name, "error": str(e)}

    def get_pod_security_context(self, pod):
        """Get security context information that might cause issues"""
        try:
            security_info = {
                "pod_security_context": {},
                "container_security_contexts": []
            }

            if pod.spec.security_context:
                security_info["pod_security_context"] = {
                    "run_as_user": pod.spec.security_context.run_as_user,
                    "run_as_group": pod.spec.security_context.run_as_group,
                    "fs_group": pod.spec.security_context.fs_group,
                    "run_as_non_root": pod.spec.security_context.run_as_non_root
                }

            for container in pod.spec.containers:
                if container.security_context:
                    security_info["container_security_contexts"].append({
                        "container": container.name,
                        "run_as_user": container.security_context.run_as_user,
                        "run_as_group": container.security_context.run_as_group,
                        "run_as_non_root": container.security_context.run_as_non_root,
                        "privileged": container.security_context.privileged,
                        "allow_privilege_escalation": container.security_context.allow_privilege_escalation
                    })

            return security_info
        except Exception as e:
            logger.error(f"Error getting security context: {e}")
            return {}

    def parse_ai_response(self, analysis_text):
        """Parse AI response to extract only RESTART_POD or HELM_ROLLBACK actions."""
        try:
            result = {
                "action": None,
                "root_cause": "",
                "confidence": "MEDIUM",
                "reasoning": "",
                "additional_checks": ""
            }

            lines = analysis_text.strip().split('\n')
            current_field = None

            for line in lines:
                line = line.strip()

                if line.startswith("ACTION:"):
                    result["action"] = line.replace("ACTION:", "").strip().upper()
                elif line.startswith("ROOT_CAUSE:"):
                    result["root_cause"] = line.replace("ROOT_CAUSE:", "").strip()
                    current_field = "root_cause"
                elif line.startswith("CONFIDENCE:"):
                    result["confidence"] = line.replace("CONFIDENCE:", "").strip()
                elif line.startswith("REASONING:"):
                    result["reasoning"] = line.replace("REASONING:", "").strip()
                    current_field = "reasoning"
                elif line.startswith("ADDITIONAL_CHECKS:"):
                    result["additional_checks"] = line.replace("ADDITIONAL_CHECKS:", "").strip()
                    current_field = "additional_checks"
                elif line and current_field:
                    result[current_field] += " " + line

            # Only allow RESTART_POD or HELM_ROLLBACK
            if result["action"] == "RESTART_POD":
                result["action"] = "RESTART"
            elif result["action"] == "HELM_ROLLBACK":
                result["action"] = "ROLLBACK"
            else:
                result["action"] = None
            return result
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return {"action": None, "error": str(e)}
    def create_ai_prompt(self, pod, namespace, logs):
        """Craft an enhanced prompt for LLM to provide actionable, agent-executable remediation."""

        # Gather comprehensive pod information
        pod_name = pod.metadata.name
        pod_status = pod.status.phase
        pod_age = ""
        if pod.metadata.creation_timestamp:
            age = datetime.datetime.now(datetime.timezone.utc) - pod.metadata.creation_timestamp
            pod_age = f"{age.days}d {age.seconds//3600}h {(age.seconds%3600)//60}m"

        # Get detailed container status information
        container_statuses = []
        init_container_statuses = []

        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                status_info = {
                    "container": cs.name,
                    "image": cs.image,
                    "restart_count": cs.restart_count,
                    "ready": cs.ready
                }

                if cs.state.waiting:
                    status_info["state"] = "waiting"
                    status_info["reason"] = cs.state.waiting.reason or "Unknown"
                    status_info["message"] = cs.state.waiting.message or ""
                elif cs.state.terminated:
                    status_info["state"] = "terminated"
                    status_info["exit_code"] = cs.state.terminated.exit_code
                    status_info["reason"] = cs.state.terminated.reason or "Unknown"
                    status_info["message"] = cs.state.terminated.message or ""
                    status_info["started_at"] = str(cs.state.terminated.started_at) if cs.state.terminated.started_at else ""
                    status_info["finished_at"] = str(cs.state.terminated.finished_at) if cs.state.terminated.finished_at else ""
                elif cs.state.running:
                    status_info["state"] = "running"
                    status_info["started_at"] = str(cs.state.running.started_at) if cs.state.running.started_at else ""

                container_statuses.append(status_info)

        # Get init container status if present
        if pod.status.init_container_statuses:
            for cs in pod.status.init_container_statuses:
                status_info = {
                    "container": cs.name,
                    "image": cs.image,
                    "restart_count": cs.restart_count,
                    "ready": cs.ready
                }

                if cs.state.waiting:
                    status_info["state"] = "waiting"
                    status_info["reason"] = cs.state.waiting.reason or "Unknown"
                    status_info["message"] = cs.state.waiting.message or ""
                elif cs.state.terminated:
                    status_info["state"] = "terminated"
                    status_info["exit_code"] = cs.state.terminated.exit_code
                    status_info["reason"] = cs.state.terminated.reason or "Unknown"
                    status_info["message"] = cs.state.terminated.message or ""
                elif cs.state.running:
                    status_info["state"] = "running"

                init_container_statuses.append(status_info)

        # Get resource requests and limits
        resource_info = []
        if pod.spec.containers:
            for container in pod.spec.containers:
                res_info = {"container": container.name}
                if container.resources:
                    if container.resources.requests:
                        res_info["requests"] = dict(container.resources.requests)
                    if container.resources.limits:
                        res_info["limits"] = dict(container.resources.limits)
                resource_info.append(res_info)

        # Get node information if available
        node_info = ""
        if pod.spec.node_name:
            node_info = f"Scheduled on node: {pod.spec.node_name}"

        # Get pod conditions
        pod_conditions = []
        if pod.status.conditions:
            for condition in pod.status.conditions:
                pod_conditions.append({
                    "type": condition.type,
                    "status": condition.status,
                    "reason": condition.reason or "",
                    "message": condition.message or "",
                    "last_transition_time": str(condition.last_transition_time) if condition.last_transition_time else ""
                })

        # Format logs with better structure
        log_text = ""
        for container_name, container_log in logs.items():
            if container_name == "events":
                log_text += f"\n\n===== Pod Events =====\n{container_log}"
            else:
                log_text += f"\n\n===== Container '{container_name}' Logs =====\n{container_log}"

        # Get helm release info if available
        helm_release = self.get_helm_release(namespace, pod_name)
        helm_info = f"Helm Release: {helm_release}" if helm_release else "Helm Release: Not detected"

        prompt = f"""
        You are an expert Kubernetes troubleshooting assistant. Analyze the following pod failure scenario and provide precise, actionable remediation.

        === POD INFORMATION ===
        Pod Name: {pod_name}
        Namespace: {namespace}
        Pod Status: {pod_status}
        Pod Age: {pod_age}
        {node_info}
        {helm_info}

        === CONTAINER STATUS DETAILS ===
        Main Containers:
        {json.dumps(container_statuses, indent=2)}

        Init Containers:
        {json.dumps(init_container_statuses, indent=2)}

        === POD CONDITIONS ===
        {json.dumps(pod_conditions, indent=2)}

        === RESOURCE CONFIGURATION ===
        {json.dumps(resource_info, indent=2)}

        === LOGS AND EVENTS ===
        {log_text}

        === ANALYSIS INSTRUCTIONS ===
        Based on the comprehensive information above, analyze the root cause and determine the most appropriate remediation action.

        Common failure patterns to consider:
        1. **Image Issues**: ImagePullBackOff, ErrImagePull, invalid image tags
        2. **Resource Constraints**: OOMKilled, CPU throttling, insufficient resources
        3. **Configuration Errors**: Invalid environment variables, missing secrets/configmaps
        4. **Network Issues**: DNS resolution, service connectivity problems
        5. **Application Errors**: Application crashes, startup failures, health check failures
        6. **Init Container Failures**: Initialization scripts failing, dependency issues
        7. **Storage Issues**: Volume mount failures, PVC issues
        8. **Security Issues**: RBAC, security context violations

        === DECISION MATRIX ===
        Choose the most appropriate action based on these guidelines:

        **RESTART_POD** - Use when:
        - Transient network/resource issues
        - Temporary infrastructure problems
        - One-time application crashes
        - Low restart count (< 5)
        - No configuration/image changes needed

        **HELM_ROLLBACK** - Use when:
        - Recent deployment introduced the issue
        - Image version problems
        - Configuration changes causing failures
        - High restart count indicating persistent issue
        - Multiple pods in same release affected
        - If the issue is due to a problematic container image (especially for CrashLoopBackOff or image pull errors)
        - especially for crashloop backoff or image pull errors kind of errors

       

        === OUTPUT FORMAT ===
        Provide your analysis in this exact format:

        ACTION: [RESTART_POD | HELM_ROLLBACK]

        ROOT_CAUSE: [Brief description of the primary issue]

        CONFIDENCE: [HIGH | MEDIUM | LOW]

        REASONING: [2-3 sentences explaining why this action is most appropriate]

        ADDITIONAL_CHECKS: [Optional: Any manual verification steps needed]

        === IMPORTANT NOTES ===
        - Focus on the most likely root cause based on error patterns
        - Consider restart count and failure frequency
        - If multiple issues exist, prioritize the most critical one
        - Provide actionable reasoning that justifies the chosen action
        - Be specific about what the action will resolve

        Analyze the failure scenario and provide your recommendation using the exact format above.
        """
        return prompt

    def send_to_mistral(self, prompt):
        """Send prompt to Mistral AI with rate limiting"""
        if not MISTRAL_API_KEY:
            logger.error("MISTRAL_API_KEY environment variable not set")
            return {"success": False, "error": "Mistral API key not configured"}

        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "mistral-small-latest",  # Using smaller model to reduce costs/rate limiting
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 400  # Increased slightly for action recommendation
        }

        try:
            response = requests.post(MISTRAL_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()

            response_json = response.json()
            analysis = response_json['choices'][0]['message']['content']
            return {"success": True, "analysis": analysis}

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Mistral AI API: {e}")
            return {"success": False, "error": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error calling Mistral AI API: {e}")
            return {"success": False, "error": str(e)}
    def process_failed_pod_enhanced(self, pod, namespace):
        """Enhanced pod analysis with comprehensive context gathering and improved chunked log readability"""
        try:
            pod_name = pod.metadata.name
            pod_uid = pod.metadata.uid

            # Gather comprehensive context
            context = {
                "pod_info": {
                    "name": pod_name,
                    "namespace": namespace,
                    "uid": pod_uid,
                    "age": self.get_pod_age(pod),
                    "node": pod.spec.node_name
                },
                "logs": self.get_pod_logs(pod, namespace),
                "related_pods": self.get_related_pods_status(namespace, pod),
                "deployment_history": self.get_recent_deployment_history(namespace, pod),
                "security_context": self.get_pod_security_context(pod),
                "helm_release": self.get_helm_release(namespace, pod_name),
                "namespace_quotas": self.get_namespace_resource_quotas(namespace)
            }

            # Add node information if pod is scheduled
            if pod.spec.node_name:
                context["node_resources"] = self.get_node_resources(pod.spec.node_name)

            # Check image availability for image-related issues
            for container in pod.spec.containers:
                if any(status.state.waiting and 
                       status.state.waiting.reason in ["ErrImagePull", "ImagePullBackOff"] 
                       for status in (pod.status.container_statuses or [])):
                    context["image_info"] = self.check_image_availability(container.image)
                    break

            # Create enhanced prompt with all context
            prompt = self.create_ai_prompt(pod, namespace, context["logs"])

            # Get AI analysis
            result = self.send_to_mistral(prompt)

            if not result.get("success", False):
                logger.error(f"\n❌❌❌\nFailed to analyze pod {pod_name}: {result.get('error', 'Unknown error')}\n❌❌❌\n")
                return False

            # Parse the enhanced response
            analysis = self.parse_ai_response(result["analysis"])

            # Abstracted chunked log for one failed pod (analysis + remediation)
            logger.info("\n==================== FAILED POD CHUNK START ====================")
            logger.info(f"FAILED POD: {pod_name} (uid={pod_uid}) in Namespace: {namespace}")
            logger.info("***************************************************************")
            logger.info("[ANALYSIS]")
            logger.info(f"ROOT CAUSE: {analysis.get('root_cause', 'Unknown')}")
            logger.info(f"RECOMMENDED ACTION: {analysis.get('action', 'None')}")
            logger.info(f"CONFIDENCE: {analysis.get('confidence', 'Unknown')}")
            logger.info(f"REASONING: {analysis.get('reasoning', 'No reasoning provided')}")
            if analysis.get('additional_checks'):
                logger.info(f"ADDITIONAL CHECKS: {analysis.get('additional_checks')}")
            logger.info("---------------------------------------------------------------")
            logger.info("[REMEDIATION]")
            # Execute action based on confidence level
            if analysis.get('confidence') == 'HIGH' or analysis.get('confidence') == 'MEDIUM':
                logger.info("Implementing remediation action for failed pod...")
                remediation_result = self.execute_remediation_action(analysis, pod, namespace, context)
                logger.info(f"Remediation result: {'SUCCESS' if remediation_result else 'NO ACTION/FAILED'}")
            else:
                logger.warning(f"Low confidence in analysis for {pod_name}, skipping automatic remediation")
                logger.info("Remediation result: SKIPPED (Low confidence)")
            logger.info("===================== FAILED POD CHUNK END =====================\n")

        except Exception as e:
            logger.error(f"\n❌ Error in enhanced pod analysis: {e}\n")
            return False

    def execute_remediation_action(self, analysis, pod, namespace, context):
        """Execute only the LLM-recommended remediation action (RESTART or ROLLBACK)."""
        action = analysis.get('action')
        pod_name = pod.metadata.name
        if action == "RESTART":
            logger.info(f"Executing RESTART action for pod {pod_name}")
            return self.restart_pod(namespace, pod_name)
        elif action == "ROLLBACK":
            helm_release = context.get('helm_release')
            if helm_release:
                logger.info(f"Executing ROLLBACK action for Helm release {helm_release}")
                return self.perform_helm_rollback(namespace, helm_release)
            else:
                logger.warning(f"Cannot perform rollback for {pod_name} - no Helm release detected")
                return False
        else:
            logger.warning(f"No valid action recommended by LLM for pod {pod_name}")
            return False

    def get_pod_age(self, pod):
        """Calculate pod age in human-readable format"""
        if pod.metadata.creation_timestamp:
            age = datetime.datetime.now(datetime.timezone.utc) - pod.metadata.creation_timestamp
            return f"{age.days}d {age.seconds//3600}h {(age.seconds%3600)//60}m"
        return "Unknown"
    def get_helm_release(self, namespace: str, pod_name: str) -> Optional[str]:
        """Get Helm release name for a pod based on labels"""
        try:
            pod = self.v1.read_namespaced_pod(pod_name, namespace)
            labels = pod.metadata.labels or {}
            
            # Common Helm-related labels
            release_name = labels.get('helm.sh/release') or labels.get('release') or labels.get('app.kubernetes.io/instance')
            
            if release_name:
                return release_name
            
            # If no direct Helm labels, try to find the owner reference chain
            owner_refs = pod.metadata.owner_references
            while owner_refs and len(owner_refs) > 0:
                owner = owner_refs[0]
                if owner.kind == 'ReplicaSet':
                    rs = self.apps_v1.read_namespaced_replica_set(owner.name, namespace)
                    rs_labels = rs.metadata.labels or {}
                    release_name = rs_labels.get('helm.sh/release') or rs_labels.get('release')
                    if release_name:
                        return release_name
                    owner_refs = rs.metadata.owner_references
                else:
                    break
                    
            return None
        except Exception as e:
            logger.error(f"Error getting Helm release for pod {pod_name}: {str(e)}")
            return None

    def perform_helm_rollback(self, namespace: str, release_name: str) -> bool:
        """Perform Helm rollback for a release to the last stable revision from ConfigMap, if available."""
        try:
            # Check if we've already attempted a rollback recently
            current_time = time.time()
            last_attempt = self.helm_rollback_attempts.get(f"{namespace}/{release_name}", 0)
            if current_time - last_attempt < 300:  # 5 minutes cooldown
                logger.info(f"Skipping rollback for {release_name} - too soon since last attempt")
                return False

            # Get last stable revision from ConfigMap
            stable_revision = self.get_stable_revision_from_configmap(namespace, release_name)
            if not stable_revision:
                logger.warning(f"No stable revision found in ConfigMap for {release_name}, falling back to last deployed revision in Helm history.")
                # Fallback: Use previous logic (last deployed revision)
                cmd = f"helm history {release_name} -n {namespace} --max 10"
                result = subprocess.run(cmd.split(), capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Error getting Helm history: {result.stderr}")
                    return False
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                last_success_revision = None
                current_revision = None
                for line in reversed(lines):
                    parts = line.split()
                    if len(parts) >= 3:
                        revision, status = parts[0], parts[6]
                        if current_revision is None:
                            current_revision = revision
                        if status.lower() == 'deployed':
                            last_success_revision = revision
                            break
                if not last_success_revision or last_success_revision == current_revision:
                    logger.info(f"No suitable revision found for rollback of {release_name}")
                    return False
                rollback_revision = last_success_revision
            else:
                rollback_revision = stable_revision

            # Perform the rollback
            cmd = f"helm rollback {release_name} {rollback_revision} -n {namespace}"
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Successfully rolled back {release_name} to revision {rollback_revision}")
                self.helm_rollback_attempts[f"{namespace}/{release_name}"] = current_time
                # After rollback, get the new revision and set it in pending ConfigMap
                new_revision = self.get_helm_release_revision(namespace, release_name)
                if new_revision:
                    self.set_pending_revision_in_configmap(namespace, release_name, new_revision)
                    logger.info(f"Set pending revision to {new_revision} for {release_name} after rollback")
                    # Start health check for the new revision
                    threading.Thread(target=self.handle_helm_post_install_or_upgrade, args=(namespace, release_name, 30), kwargs={"revision": new_revision}, daemon=True).start()
                else:
                    logger.warning(f"Could not determine new revision for {release_name} after rollback")
                return True
            else:
                logger.error(f"Error rolling back {release_name}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error during Helm rollback for {release_name}: {str(e)}")
            return False

    def update_stable_revision_configmap(self, namespace: str, release_name: str, revision: str):
        """Update or create a ConfigMap to track the last stable revision for a Helm release."""
        configmap_name = "helm-stable-revisions"
        try:
            cm = None
            try:
                cm = self.v1.read_namespaced_config_map(configmap_name, namespace)
            except client.exceptions.ApiException as e:
                if e.status != 404:
                    raise
            if cm is None:
                # Create new ConfigMap
                body = client.V1ConfigMap(
                    metadata=client.V1ObjectMeta(name=configmap_name),
                    data={release_name: revision}
                )
                self.v1.create_namespaced_config_map(namespace, body)
                logger.info(f"Created ConfigMap {configmap_name} with {release_name}: {revision}")
            else:
                # Update existing ConfigMap
                data = cm.data or {}
                data[release_name] = revision
                body = {"data": data}
                self.v1.patch_namespaced_config_map(configmap_name, namespace, body)
                logger.info(f"Updated ConfigMap {configmap_name} with {release_name}: {revision}")
        except Exception as e:
            logger.error(f"Error updating stable revision ConfigMap: {e}")

    def get_stable_revision_from_configmap(self, namespace: str, release_name: str) -> str:
        """Get the last stable revision for a Helm release from the ConfigMap."""
        configmap_name = "helm-stable-revisions"
        try:
            cm = self.v1.read_namespaced_config_map(configmap_name, namespace)
            if cm and cm.data and release_name in cm.data:
                return cm.data[release_name]
        except client.exceptions.ApiException as e:
            if e.status != 404:
                logger.error(f"Error reading stable revision ConfigMap: {e}")
        return None

    def is_release_pods_healthy(self, namespace: str, release_name: str) -> bool:
        """Check if all pods for a Helm release are running, ready, and all init containers have succeeded."""
        try:
            pods = self.v1.list_namespaced_pod(namespace=namespace)
            for pod in pods.items:
                labels = pod.metadata.labels or {}
                pod_release = labels.get('helm.sh/release') or labels.get('release') or labels.get('app.kubernetes.io/instance')
                if pod_release == release_name:
                    # Check pod phase
                    if pod.status.phase != "Running":
                        return False
                    # Check all containers are ready
                    if not pod.status.container_statuses or not all(cs.ready for cs in pod.status.container_statuses):
                        return False
                    # Check all init containers have completed successfully
                    init_statuses = pod.status.init_container_statuses or []
                    for cs in init_statuses:
                        # If waiting or terminated with non-zero exit code, not healthy
                        if cs.state.waiting is not None:
                            return False
                        if cs.state.terminated is not None and cs.state.terminated.exit_code != 0:
                            return False
            return True
        except Exception as e:
            logger.error(f"Error checking pod health for release {release_name}: {e}")
            return False

    def get_helm_release_revision(self, namespace: str, release_name: str) -> Optional[str]:
        """Get the current revision number for a Helm release."""
        try:
            cmd = f"helm list -n {namespace} --filter ^{release_name}$ --output json"
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Error getting Helm release revision: {result.stderr}")
                return None
            releases = json.loads(result.stdout)
            if releases and len(releases) > 0:
                return str(releases[0].get("revision"))
        except Exception as e:
            logger.error(f"Error getting Helm release revision: {e}")
        return None

    # --- Per-release health check control ---
    _health_check_locks = {}
    _health_check_abort_flags = {}

    def handle_helm_post_install_or_upgrade(self, namespace: str, release_name: str, wait_seconds: int = 30, check_interval: int = 5, revision: str = None):
        """
        Health check for new Helm revision: only update stable CM if healthy, clear pending if not. Never rollback or delete pods automatically.
        """
        key = f"{namespace}__{release_name}"
        if key not in self._health_check_locks:
            self._health_check_locks[key] = threading.Lock()
        if key not in self._health_check_abort_flags:
            self._health_check_abort_flags[key] = threading.Event()

        with self._health_check_locks[key]:
            while self.agent_active_event.is_set():
                time.sleep(1)

            self._health_check_abort_flags[key].set()
            self._health_check_abort_flags[key] = threading.Event()
            abort_flag = self._health_check_abort_flags[key]

            target_revision = self.get_helm_release_revision(namespace, release_name)
            if not target_revision:
                logger.warning(f"No Helm revision found for release {release_name} in {namespace}, aborting health check.")
                return

            # Prevent repeated health checks for already stable revisions
            stable_revision = self.get_stable_revision_from_configmap(namespace, release_name)
            if stable_revision == target_revision:
                logger.info(f"Revision {target_revision} for release {release_name} is already marked stable. Skipping health check.")
                self.clear_pending_revision_in_configmap(namespace, release_name)
                return

            self.set_pending_revision_in_configmap(namespace, release_name, target_revision)
            logger.info(f"Detected revision {target_revision} for release {release_name}, starting health check.")
            waited = 0
            while waited < wait_seconds:
                if abort_flag.is_set():
                    logger.info(f"Health check for {release_name} in {namespace} aborted due to new revision.")
                    return
                current_revision = self.get_helm_release_revision(namespace, release_name)
                if current_revision != target_revision:
                    logger.info(f"Detected newer Helm revision {current_revision} for {release_name}, aborting and starting new check.")
                    self.set_pending_revision_in_configmap(namespace, release_name, current_revision)
                    threading.Thread(target=self.handle_helm_post_install_or_upgrade, args=(namespace, release_name, wait_seconds), kwargs={"revision": current_revision}, daemon=True).start()
                    return
                time.sleep(check_interval)
                waited += check_interval

            # After 30s, check pod health
            if self.is_release_pods_healthy(namespace, release_name):
                self.update_stable_revision_configmap(namespace, release_name, target_revision)
                logger.info(f"Revision {target_revision} for release {release_name} marked stable.")
            else:
                logger.info(f"Revision {target_revision} for release {release_name} not stable")
            self.clear_pending_revision_in_configmap(namespace, release_name)

    def watch_deployments_for_helm_events(self, namespace: str = None):
        """
        Watch for Deployment events and process Helm install/upgrade events.
        Only log stability after health check, never rollback or delete pods automatically.
        """
        w = watch.Watch()
        logger.info("Starting Deployment watch for Helm install/upgrade events...")

        self.reconcile_pending_configmap_with_helm()
        self.process_pending_revisions_on_startup()

        try:
            # Check if we've already attempted a rollback recently
            current_time = time.time()
            last_attempt = self.helm_rollback_attempts.get(f"{namespace}/{release_name}", 0)
            if current_time - last_attempt < 300:  # 5 minutes cooldown
                logger.info(f"Skipping rollback for {release_name} - too soon since last attempt")
                return False

            # Get last stable revision from ConfigMap
            stable_revision = self.get_stable_revision_from_configmap(namespace, release_name)
            if not stable_revision:
                logger.warning(f"No stable revision found in ConfigMap for {release_name}, falling back to last deployed revision in Helm history.")
                # Fallback: Use previous logic (last deployed revision)
                cmd = f"helm history {release_name} -n {namespace} --max 10"
                result = subprocess.run(cmd.split(), capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Error getting Helm history: {result.stderr}")
                    return False
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                last_success_revision = None
                current_revision = None
                for line in reversed(lines):
                    parts = line.split()
                    if len(parts) >= 3:
                        revision, status = parts[0], parts[6]
                        if current_revision is None:
                            current_revision = revision
                        if status.lower() == 'deployed':
                            last_success_revision = revision
                            break
                if not last_success_revision or last_success_revision == current_revision:
                    logger.info(f"No suitable revision found for rollback of {release_name}")
                    return False
                rollback_revision = last_success_revision
            else:
                rollback_revision = stable_revision

            # Perform the rollback
            cmd = f"helm rollback {release_name} {rollback_revision} -n {namespace}"
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Successfully rolled back {release_name} to revision {rollback_revision}")
                self.helm_rollback_attempts[f"{namespace}/{release_name}"] = current_time
                # Immediately update both stable and pending ConfigMaps to prevent duplicate rollbacks and watcher triggers
                self.update_stable_revision_configmap(namespace, release_name, rollback_revision)
                self.clear_pending_revision_in_configmap(namespace, release_name)
                return True
            else:
                logger.error(f"Error rolling back {release_name}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error during Helm rollback for {release_name}: {str(e)}")
            return False
            failed = False
            if pod_status in ["Failed", "Unknown"]:
                failed = True
            if any(cs.state.waiting and cs.state.waiting.reason in ["CrashLoopBackOff", "Error", "ErrImagePull", "ImagePullBackOff"] for cs in container_statuses):
                failed = True
            if any(cs.state.terminated and cs.state.terminated.exit_code != 0 for cs in container_statuses):
                failed = True
            if any(cs.state.waiting and cs.state.waiting.reason in ["CrashLoopBackOff", "Error", "ErrImagePull", "ImagePullBackOff"] for cs in init_container_statuses):
                failed = True
            if any(cs.state.terminated and cs.state.terminated.exit_code != 0 for cs in init_container_statuses):
                failed = True
            pod_uid = pod.metadata.uid
            if failed and pod_uid not in self.already_analyzed_pods:
                logger.info(f"Found failed pod: {namespace}/{pod.metadata.name} (uid={pod_uid})")
                failed_pods.append((pod, pod_uid))
        return failed_pods

    def run(self):
        """Main loop: watches Helm events in background, and processes failed pods one at a time using process_failed_pod_enhanced."""
        logger.info("\n\nStarting Kubernetes Error Analysis Agent (with deployment watch and sequential failed pod analysis)\n\n")

        # Start the deployment watcher in a background thread
        watcher_thread = threading.Thread(target=self.watch_deployments_for_helm_events, kwargs={"namespace": None}, daemon=True)
        watcher_thread.start()

        while True:
            try:
                namespaces = self.get_all_namespaces()
                logger.info(f"\nFound {len(namespaces)} namespaces in the cluster.\n")

                for namespace in namespaces:
                    logger.info(f"\nChecking for failed pods in namespace: {namespace} ...\n")
                    failed_pods = self.get_failed_pods(namespace)
                    logger.info(f"Found {len(failed_pods)} failed pods in namespace {namespace}\n")

                    for pod, pod_uid in failed_pods:
                        # Mark pod as analyzed to avoid duplicate processing
                        self.already_analyzed_pods.add(f"{namespace}/{pod_uid}")

                        # Process failed pod one at a time, sequentially
                        logger.info(f"Analyzing failed pod {pod.metadata.name} (uid={pod_uid}) in namespace {namespace} ...\n")
                        self.process_failed_pod_enhanced(pod, namespace)
                        time.sleep(REQUEST_DELAY)

                logger.info(f"\nWaiting {CHECK_INTERVAL} seconds before next failed pod scan across all namespaces...\n{'='*80}\n")
                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                logger.error(f"\nError in main loop: {str(e)}\n")
                logger.error(traceback.format_exc())
                time.sleep(10)
if __name__ == "__main__":
    try:
        print("success-14")
        agent = K8sErrorAnalysisAgent()
        agent.run()
    except Exception as e:
        logger.error(f"Fatal error starting agent: {e}")
        logger.error(traceback.format_exc())
        exit(1)
