flowchart TD
    A[Start Agent] --> B[Watch for Helm Events & Failed Pods]
    B --> C{Helm Upgrade/Install Detected?}
    C -- Yes --> D[Start Health Check for New Revision]
    D --> E{Pods Healthy?}
    E -- Yes --> F[Mark Revision as Stable in ConfigMap]
    E -- No --> G[Clear Pending Revision (No Rollback)]
    C -- No --> H[Scan for Failed Pods in All Namespaces]
    H --> I{Failed Pod Found?}
    I -- Yes --> J[Gather Pod Logs & Context]
    J --> K[Send to Mistral AI for Analysis]
    K --> L{AI Recommendation}
    L -- RESTART_POD --> M[Restart Pod]
    L -- HELM_ROLLBACK --> N[Rollback Helm Release to Last Stable Revision]
    N --> O[Update Stable & Pending ConfigMaps]
    O --> P[Start Health Check for New Revision]
    P --> Q{Pods Healthy?}
    Q -- Yes --> R[Mark Revision as Stable]
    Q -- No --> S[Clear Pending Revision]
    I -- No --> T[Wait & Repeat Scan]
    F --> T
    G --> T
    M --> T
    R --> T
    S --> T
