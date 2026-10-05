// GENERATED from docs/api/openapi.yaml by `npm run gen`. Do not edit.
export interface paths {
    "/v1/auth/signup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["signup"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["login"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Rotates the refresh token (httpOnly cookie `gc_refresh`). Reuse of a rotated token revokes the family. */
        post: operations["refresh"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["logout"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getMe"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["listWorkspaces"];
        put?: never;
        post: operations["createWorkspace"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["getWorkspace"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/members": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listMembers"];
        put?: never;
        post: operations["addMember"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/projects": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listProjects"];
        put?: never;
        post: operations["createProject"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/sources": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listSources"];
        put?: never;
        post: operations["createSource"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/uploads": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description Stores the file and enqueues an ingest job. Returns the upload and its job id. */
        post: operations["createUpload"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/ingest-jobs": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listIngestJobs"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/ingest-jobs/{job}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                job: components["parameters"]["job"];
            };
            cookie?: never;
        };
        get: operations["getIngestJob"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/ingest-jobs/{job}/events": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                job: components["parameters"]["job"];
            };
            cookie?: never;
        };
        /**
         * @description Server-Sent Events. Each event: `id: <seq>`, `event: progress|done|failed`, `data: <IngestJobEvent JSON>`.
         *     Resume with the `Last-Event-ID` header. The stream ends after `done` or `failed`. Heartbeat comment every 15 s.
         */
        get: operations["streamIngestJobEvents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["listModels"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/usage/summary": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        /** @description Overview tiles plus a daily trend (overview screen). */
        get: operations["usageSummary"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/usage/series/tokens": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
                bucket?: components["parameters"]["bucket"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        /** @description Token mix over time (input, cache_read, cache_write, output), optionally split by model. */
        get: operations["tokenSeries"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/usage/series/call-size": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        /** @description Histogram of per-call context tokens (log2 bins) and the outlier calls above the bulk-injection threshold. */
        get: operations["callSizeHistogram"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/usage/compare": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        /** @description Tokens and cost per correct task, accuracy, with P10-P90 ranges, grouped by configuration dimensions. */
        get: operations["compareConfigs"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/usage/calls": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listCalls"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/usage/sessions": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listSessions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/usage/tasks": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listTasks"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/usage/tasks/{task}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                task: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** @description Set task features or outcome (user-labelled). Emits usage.task.outcome_set. */
        patch: operations["updateTask"];
        trace?: never;
    };
    "/v1/workspaces/{ws}/budgets": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listBudgets"];
        put?: never;
        /** @description Budget changes are audited (budget.create). */
        post: operations["createBudget"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/budgets/{budget}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                budget: components["parameters"]["budget"];
            };
            cookie?: never;
        };
        get: operations["getBudget"];
        put?: never;
        post?: never;
        delete: operations["archiveBudget"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/budgets/{budget}/burn": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                budget: components["parameters"]["budget"];
            };
            cookie?: never;
        };
        /** @description Cumulative use against the limit for both measures, and the projected exhaustion with a band. */
        get: operations["budgetBurn"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/quota/alerts": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listBudgetAlerts"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/estimates": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listEstimates"];
        put?: never;
        post: operations["createEstimate"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/estimates/{estimate}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                estimate: string;
            };
            cookie?: never;
        };
        get: operations["getEstimate"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/estimation/accuracy": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["estimateAccuracy"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/advisor/rules": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listAdvisorRules"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/advisor/findings": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listFindings"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listProposals"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/proposals/{proposal}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                proposal: components["parameters"]["proposal"];
            };
            cookie?: never;
        };
        get: operations["getProposal"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/proposals/{proposal}/decision": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                proposal: components["parameters"]["proposal"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * @description accept / reject / apply. `apply` runs policy check, then quota.check, then requires `confirm: true` from the
         *     deciding user. Every call is written to the audit log. A refused apply sets state `blocked` with the reason.
         */
        post: operations["decideProposal"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/simulations": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["createSimulation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/simulations/{simulation}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                simulation: string;
            };
            cookie?: never;
        };
        get: operations["getSimulation"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/profile": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["getProfile"];
        put: operations["putProfile"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/profile/stats": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["getPersonalStats"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/profile/recommendations": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listRecommendations"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/reports": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listReports"];
        put?: never;
        post: operations["generateReport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/reports/{report}/export": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                report: string;
            };
            cookie?: never;
        };
        get: operations["exportReport"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/notifications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["listNotifications"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/notifications/{notification}/read": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                notification: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["markNotificationRead"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/notification-prefs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getNotificationPrefs"];
        put: operations["putNotificationPrefs"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/audit-log": {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        /** @description Admin only. */
        get: operations["listAuditLog"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/integrations": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listIntegrations"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/provider-credentials": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        /** @description Returns references only (fingerprint, last4). Never the secret. */
        get: operations["listProviderCredentials"];
        put?: never;
        /** @description Write-only. The secret is encrypted at once; the response holds only the reference. Audited. */
        post: operations["storeProviderCredential"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/provider-credentials/{credential}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                credential: string;
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete: operations["revokeProviderCredential"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/monitor/sources": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        /** @description Registered local .ga directories. In the desktop sidecar ws is the nil UUID and the one directory is preset. */
        get: operations["listMonitorSources"];
        put?: never;
        /** @description Admin only, audited. Registers a path to read; the platform never writes inside it. */
        post: operations["registerMonitorSource"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/monitor/sources/{source}/snapshot": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                source: components["parameters"]["source"];
            };
            cookie?: never;
        };
        get: operations["monitorSnapshot"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/monitor/sources/{source}/events": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                source: components["parameters"]["source"];
            };
            cookie?: never;
        };
        /**
         * @description Server-Sent Events of MonitorEvent (monitor-event/1). `id: <seq>`, `event: <kind>`, `data: <MonitorEvent JSON>`.
         *     Resume with Last-Event-ID. Heartbeat comment every 15 s. Read-only: there is no control endpoint.
         */
        get: operations["streamMonitorEvents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/monitor/sources/{source}/recordings": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                source: components["parameters"]["source"];
            };
            cookie?: never;
        };
        get: operations["listMonitorRecordings"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/monitor/sources/{source}/recordings/{recording}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                source: components["parameters"]["source"];
                recording: string;
            };
            cookie?: never;
        };
        /** @description The recorded MonitorEvent JSONL, for timeline replay. */
        get: operations["getMonitorRecording"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        get: operations["listRuns"];
        put?: never;
        /** @description Starts only from an applied proposal (approval gate + budget check). Audited. */
        post: operations["startRun"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/runs/{run}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        get: operations["getRun"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/runs/{run}/events": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        /** @description SSE of run_events (node.started, turn, wait, node.retired, item.state). Resume with Last-Event-ID. */
        get: operations["streamRunEvents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/runs/{run}/timeline": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        get: operations["runTimeline"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/runs/{run}/flow": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        get: operations["runFlow"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/runs/{run}/network": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        get: operations["runNetwork"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{ws}/runs/{run}/verdicts": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        get: operations["runVerdicts"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        Error: {
            code: string;
            /** @description Never contains secrets or uploaded content. */
            message: string;
            request_id?: string;
        };
        /** @enum {string} */
        Provenance: "MEASURED" | "CALCULATED" | "ESTIMATED" | "SIMULATED";
        /** @enum {string} */
        Measure: "list" | "cli";
        /** @enum {string} */
        Unit: "tokens" | "microusd" | "calls" | "tasks" | "permille" | "ms" | "count";
        /** @description One number with its unit and provenance. `value` null = unknown (never 0 for unknown). */
        Metric: {
            value: number | null;
            unit: components["schemas"]["Unit"];
            provenance: components["schemas"]["Provenance"];
            /** @description Share of calls that reported this value (cli cost). */
            coverage_permille?: number;
        };
        /** @description P10 / P50 / P90 of one quantity. */
        Range: {
            p10: number;
            p50: number;
            p90: number;
            unit: components["schemas"]["Unit"];
            provenance: components["schemas"]["Provenance"];
        };
        Series: {
            name: string;
            unit: components["schemas"]["Unit"];
            provenance: components["schemas"]["Provenance"];
            points: [
                string,
                number | null
            ][];
        };
        SeriesSet: {
            bucket: string;
            series: components["schemas"]["Series"][];
        };
        Period: {
            /** Format: date */
            from: string;
            /** Format: date */
            to: string;
        };
        SignupRequest: {
            /** Format: email */
            email: string;
            password: string;
            display_name?: string;
        };
        LoginRequest: {
            /** Format: email */
            email: string;
            password: string;
        };
        /** @description Access token in the body; the refresh token is set as an httpOnly, Secure, SameSite=Strict cookie only. */
        TokenPair: {
            access_token: string;
            expires_in: number;
        };
        User: {
            /** Format: uuid */
            id: string;
            email: string;
            display_name?: string;
        };
        /** @enum {string} */
        Role: "admin" | "developer" | "viewer";
        Workspace: {
            /** Format: uuid */
            id: string;
            name: string;
            slug: string;
            role: components["schemas"]["Role"];
        };
        WorkspaceCreate: {
            name: string;
        };
        Member: {
            /** Format: uuid */
            user_id: string;
            email?: string;
            role: components["schemas"]["Role"];
        };
        MemberAdd: {
            /** Format: email */
            email: string;
            role: components["schemas"]["Role"];
        };
        Project: {
            /** Format: uuid */
            id: string;
            name: string;
            language?: string | null;
            repo_size_loc?: number | null;
        };
        ProjectCreate: {
            name: string;
            repo_url?: string;
            language?: string;
            repo_size_loc?: number;
        };
        /** @enum {string} */
        SourceKind: "claude_code" | "ga_l0" | "anthropic_export" | "openai_export" | "otel";
        Source: {
            /** Format: uuid */
            id: string;
            /** @enum {string} */
            kind: "upload" | "anthropic_api" | "openai_api" | "otel" | "ga_runner";
            name: string;
            /** Format: uuid */
            project_id?: string | null;
        };
        SourceCreate: {
            /** @enum {string} */
            kind: "upload";
            name: string;
            /** Format: uuid */
            project_id?: string;
        };
        Upload: {
            /** Format: uuid */
            id: string;
            filename: string;
            size_bytes: number;
            sha256: string;
            /** Format: uuid */
            job_id: string;
        };
        /** @enum {string} */
        IngestState: "queued" | "parsing" | "normalizing" | "loading" | "analyzing" | "done" | "failed";
        IngestJob: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            upload_id: string;
            state: components["schemas"]["IngestState"];
            source_kind?: components["schemas"]["SourceKind"] | null;
            parser?: string | null;
            inserted: number;
            duplicates: number;
            rejected: number;
            last_error_code?: string | null;
            /** Format: date-time */
            created_at?: string;
            /** Format: date-time */
            finished_at?: string | null;
        };
        IngestJobEvent: {
            seq: number;
            stage: components["schemas"]["IngestState"];
            pct: number;
            counts: {
                inserted?: number;
                duplicates?: number;
                rejected?: number;
            };
        };
        ModelWithPrice: {
            id: string;
            provider: string;
            /** @enum {string} */
            family: "claude" | "gpt" | "gemini";
            tier: number;
            min_cache_tokens?: number | null;
            price: {
                version: number;
                /** Format: date */
                effective_from?: string;
                input_per_mtok_microusd: number;
                output_per_mtok_microusd: number;
                cache_read_per_mtok_microusd: number;
                cache_write_5m_per_mtok_microusd: number;
                cache_write_1h_per_mtok_microusd: number;
            };
        };
        UsageSummary: {
            period: components["schemas"]["Period"];
            tiles: {
                total_tokens: components["schemas"]["Metric"];
                cost_list: components["schemas"]["Metric"];
                cost_cli: components["schemas"]["Metric"];
                correct_tasks: components["schemas"]["Metric"];
                cost_list_per_correct: components["schemas"]["Metric"];
                cost_cli_per_correct: components["schemas"]["Metric"];
                budget_use: components["schemas"]["Metric"];
            };
            trend: components["schemas"]["SeriesSet"];
        };
        Histogram: {
            unit: components["schemas"]["Unit"];
            provenance: components["schemas"]["Provenance"];
            threshold: number;
            bins: {
                lo: number;
                hi: number;
                count: number;
            }[];
            outliers: {
                call_id: number;
                context_tokens: number;
                model_id: string;
                /** Format: date-time */
                occurred_at?: string;
            }[];
        };
        Comparison: {
            dims: string[];
            groups: {
                key: {
                    [key: string]: string;
                };
                tasks: number;
                correct: number;
                accuracy?: components["schemas"]["Metric"];
                tokens_per_correct: components["schemas"]["Range"];
                cost_list_per_correct: components["schemas"]["Range"];
                cost_cli_per_correct?: components["schemas"]["Range"];
            }[];
        };
        Call: {
            id: number;
            /** Format: date-time */
            occurred_at: string;
            /** @enum {string} */
            time_basis?: "reported" | "ingested";
            model_id: string;
            provider: string;
            source_kind: components["schemas"]["SourceKind"];
            role?: string | null;
            /** Format: uuid */
            session_id?: string | null;
            /** Format: uuid */
            task_id?: string | null;
            input_tokens?: number | null;
            cache_read_tokens?: number | null;
            cache_write_tokens?: number | null;
            output_tokens?: number | null;
            context_tokens?: number | null;
            /** @description CALCULATED */
            cost_list_microusd?: number | null;
            /** @description MEASURED */
            cost_cli_microusd?: number | null;
        };
        CallPage: {
            items: components["schemas"]["Call"][];
            next_cursor?: string | null;
        };
        Session: {
            /** Format: uuid */
            id: string;
            client: string;
            /** Format: date-time */
            started_at?: string | null;
            /** Format: date-time */
            ended_at?: string | null;
            calls: number;
            cost_list_microusd?: number | null;
            cost_cli_microusd?: number | null;
        };
        SessionPage: {
            items: components["schemas"]["Session"][];
            next_cursor?: string | null;
        };
        Task: {
            /** Format: uuid */
            id: string;
            external_ref?: string | null;
            /** @enum {string} */
            kind: "feature" | "bug" | "refactor" | "docs" | "other";
            structure?: string | null;
            context_mode?: string | null;
            model_primary?: string | null;
            /** @enum {string} */
            outcome: "correct" | "incorrect" | "unknown";
            calls: number;
            total_tokens?: number | null;
            cost_list_microusd?: number | null;
            cost_cli_microusd?: number | null;
        };
        TaskPage: {
            items: components["schemas"]["Task"][];
            next_cursor?: string | null;
        };
        TaskUpdate: {
            /** @enum {string} */
            kind?: "feature" | "bug" | "refactor" | "docs" | "other";
            /** @enum {string} */
            outcome?: "correct" | "incorrect" | "unknown";
            /** @enum {string} */
            structure?: "A" | "B" | "C" | "single";
            /** @enum {string} */
            context_mode?: "bulk" | "selective" | "fresh";
        };
        Budget: {
            /** Format: uuid */
            id: string;
            /** @enum {string} */
            scope: "workspace" | "project" | "task";
            /** Format: uuid */
            project_id?: string | null;
            /** @enum {string} */
            period: "day" | "month" | "task";
            measure: components["schemas"]["Measure"];
            limit_microusd: number;
            thresholds: number[];
            /** @enum {string} */
            action_at_limit?: "alert" | "stop";
            /** @description Current period use in both measures, always side by side. */
            used: {
                list: components["schemas"]["Metric"];
                cli: components["schemas"]["Metric"];
            };
        };
        BudgetCreate: {
            /** @enum {string} */
            scope: "workspace" | "project" | "task";
            /** Format: uuid */
            project_id?: string;
            /** @enum {string} */
            period: "day" | "month" | "task";
            measure: components["schemas"]["Measure"];
            limit_microusd: number;
            thresholds?: number[];
        };
        BurnSeries: {
            /** Format: uuid */
            budget_id: string;
            limit_microusd: number;
            cumulative: {
                list: components["schemas"]["Series"];
                cli: components["schemas"]["Series"];
            };
            projection: {
                p10: components["schemas"]["Series"];
                p50: components["schemas"]["Series"];
                p90: components["schemas"]["Series"];
                /** Format: date-time */
                exhaust_at_p10?: string | null;
                /** Format: date-time */
                exhaust_at_p50: string | null;
                /** Format: date-time */
                exhaust_at_p90?: string | null;
            };
        };
        BudgetAlert: {
            /** Format: uuid */
            id: string;
            /** Format: uuid */
            budget_id: string;
            threshold: number;
            used_microusd: number;
            /** Format: date-time */
            raised_at: string;
        };
        EstimateRequest: {
            /** @description Used for features only; stored as hash + length. */
            description: string;
            /** @enum {string} */
            task_kind: "feature" | "bug" | "refactor" | "docs" | "other";
            repo_size_loc?: number;
            language?: string;
            model: string;
            /** @enum {string} */
            structure?: "A" | "B" | "C" | "single";
            /** @enum {string} */
            context_mode?: "bulk" | "selective" | "fresh";
            context_cap_tokens?: number;
            /** Format: uuid */
            project_id?: string;
        };
        Estimate: {
            /** Format: uuid */
            id: string;
            input_tokens: components["schemas"]["Range"];
            cache_tokens: components["schemas"]["Range"];
            output_tokens: components["schemas"]["Range"];
            cost_list: components["schemas"]["Range"];
            cost_cli?: components["schemas"]["Range"] | null;
            calls: components["schemas"]["Range"];
            duration_ms?: components["schemas"]["Range"] | null;
            success_prob: components["schemas"]["Metric"];
            evidence: {
                n: number;
                task_ids: string[];
                /** @enum {string} */
                basis?: "global_prior" | "workspace" | "user" | "blended";
            };
            estimator: {
                version: number;
                mape_permille: number | null;
            };
            recommended_config?: {
                model?: string;
                structure?: string;
                context_cap_tokens?: number;
            };
        };
        Accuracy: {
            n: number;
            mape_tokens: components["schemas"]["Metric"];
            mape_cost: components["schemas"]["Metric"];
            coverage_p10_p90: components["schemas"]["Metric"];
            series: components["schemas"]["SeriesSet"];
        };
        AdvisorRule: {
            /** @enum {string} */
            rule_id: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7";
            name: string;
            enabled: boolean;
            params: Record<string, never>;
        };
        Finding: {
            /** Format: uuid */
            id: string;
            rule_id: string;
            period: components["schemas"]["Period"];
            savings: components["schemas"]["Range"];
            savings_tokens: components["schemas"]["Metric"];
            measure?: components["schemas"]["Measure"];
            evidence_call_ids: number[];
            evidence_task_ids?: string[];
            detail?: Record<string, never>;
            /** Format: uuid */
            proposal_id: string | null;
        };
        /** @enum {string} */
        ProposalState: "proposed" | "accepted" | "rejected" | "applied" | "expired" | "blocked";
        Proposal: {
            /** Format: uuid */
            id: string;
            /** @enum {string} */
            origin: "advisor" | "simulation" | "profile" | "run_node";
            origin_ref: string;
            /** @enum {string} */
            kind: "config_export" | "budget_change" | "router_tier" | "context_cap" | "template" | "repo_change";
            change: Record<string, never>;
            expected_savings?: components["schemas"]["Metric"];
            state: components["schemas"]["ProposalState"];
            blocked_reason?: string | null;
            decisions?: {
                decision?: string;
                /** Format: uuid */
                decided_by?: string;
                /** Format: date-time */
                decided_at?: string;
                policy_ok?: boolean;
                budget_ok?: boolean;
            }[];
        };
        ProposalDecision: {
            /** @enum {string} */
            decision: "accept" | "reject" | "apply";
            /** @description Required true for apply. */
            confirm?: boolean;
            note?: string;
        };
        Assumption: {
            /** @enum {string} */
            kind: "model_swap" | "context_cap" | "node_count" | "cache_prefix_fixed" | "structure";
            value: unknown;
            from?: unknown;
        };
        SimulationRequest: {
            assumptions: components["schemas"]["Assumption"][];
            basis: {
                /** Format: date-time */
                from: string;
                /** Format: date-time */
                to: string;
                /** Format: uuid */
                project_id?: string;
            };
        };
        Simulation: {
            /** Format: uuid */
            id: string;
            assumptions: components["schemas"]["Assumption"][];
            basis: {
                /** Format: date-time */
                from: string;
                /** Format: date-time */
                to: string;
                calls: number;
                tasks: number;
                price_version: number;
                stats_version?: number | null;
            };
            result: {
                baseline: {
                    [key: string]: components["schemas"]["Metric"];
                };
                simulated: {
                    [key: string]: components["schemas"]["Range"];
                };
            };
        };
        Profile: {
            monthly_budget_microusd?: number | null;
            task_budget_microusd?: number | null;
            quality_floor_permille?: number | null;
            preferred_models?: string[];
            preferred_providers?: string[];
            /** @enum {string|null} */
            billing_mode?: "subscription" | "api" | "mixed" | null;
            team_size?: number | null;
            /** @default false */
            store_bodies: boolean;
        };
        PersonalStat: {
            task_kind: string;
            model_id: string;
            structure: string;
            context_mode: string;
            tasks: number;
            correct: number;
            first_try_success?: number;
            tokens_per_correct?: components["schemas"]["Metric"];
            cost_list_per_correct?: components["schemas"]["Metric"];
            cost_cli_per_correct?: components["schemas"]["Metric"];
        };
        Recommendation: {
            /** Format: uuid */
            id: string;
            headline: string;
            current_config: Record<string, never>;
            recommended_config: Record<string, never>;
            saving: components["schemas"]["Metric"];
            evidence_n: number;
            /** Format: uuid */
            proposal_id?: string | null;
        };
        Report: {
            /** Format: uuid */
            id: string;
            period: components["schemas"]["Period"];
            body: Record<string, never>;
            /** Format: date-time */
            created_at?: string;
        };
        Notification: {
            /** Format: uuid */
            id: string;
            kind: string;
            ref?: string | null;
            text: string;
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            read_at?: string | null;
        };
        NotificationPref: {
            kind: string;
            /** @enum {string} */
            channel: "in_app" | "email" | "slack";
            enabled: boolean;
        };
        AuditEntry: {
            id: number;
            /** Format: date-time */
            at: string;
            /** Format: uuid */
            actor_user_id?: string | null;
            /** @enum {string} */
            actor_kind: "user" | "system" | "worker" | "run_node";
            action: string;
            target_kind: string;
            target_id: string;
            detail?: Record<string, never>;
        };
        AuditPage: {
            items: components["schemas"]["AuditEntry"][];
            next_cursor?: string | null;
        };
        Integration: {
            /** Format: uuid */
            id: string;
            /** @enum {string} */
            kind: "github" | "slack" | "email";
            config?: Record<string, never>;
        };
        CredentialCreate: {
            /** @enum {string} */
            provider: "anthropic" | "openai" | "gemini" | "github" | "slack";
            secret: string;
        };
        /** @description A reference to a stored provider key. There is deliberately no field that can hold the secret. */
        CredentialRef: {
            /** Format: uuid */
            id: string;
            provider: string;
            fingerprint: string;
            last4: string;
            /** Format: date-time */
            created_at: string;
            /** Format: date-time */
            revoked_at?: string | null;
        };
        Run: {
            /** Format: uuid */
            id: string;
            /** @enum {string} */
            state: "queued" | "running" | "stopping" | "stopped" | "done" | "failed";
            ga_version: string;
            /** Format: date-time */
            started_at?: string | null;
            /** Format: date-time */
            ended_at?: string | null;
        };
        Timeline: {
            lanes: {
                role: string;
                node_id: string;
                spans: {
                    /** @enum {string} */
                    kind: "turn" | "wait" | "idle";
                    /** Format: date-time */
                    start: string;
                    /** Format: date-time */
                    end: string;
                    tokens?: number | null;
                }[];
            }[];
        };
        Funnel: {
            stages: {
                /** @enum {string} */
                stage: "queued" | "running" | "judged" | "integrated";
                count: number;
                dropped?: number;
            }[];
        };
        Network: {
            nodes: {
                id: string;
                role: string;
                tokens?: number;
                budget_used_permille?: number;
            }[];
            edges: {
                from: string;
                to: string;
                messages: number;
                tokens_est?: number;
                pi_weight_permille?: number | null;
            }[];
        };
        Verdict: {
            item_id: string;
            tests_passed: number;
            tests_failed: number;
            mutants_caught?: number | null;
            mutants_total?: number | null;
            preexisting_failures?: number;
            /** @enum {string} */
            verdict: "pass" | "fail" | "partial";
        };
        MonitorSource: {
            /** Format: uuid */
            id: string;
            label: string;
            path: string;
            reachable?: boolean;
        };
        /** @description monitor-event/1. kind is a signal name of design/encoding.json (l0:<type>, file:<signal>, derived:<mood>). */
        MonitorEvent: {
            seq: number;
            /**
             * Format: date-time
             * @description When the reader first saw the change (ga 0.6 L0 has no time).
             */
            observed_at: string;
            kind: string;
            node?: string | null;
            role?: string | null;
            item?: string | null;
            peer?: string | null;
            data: Record<string, never>;
            source_file?: string | null;
            provenance: components["schemas"]["Provenance"];
        };
        MonitorFigure: {
            node: string;
            role: string;
            shape_index: number;
            /** @enum {string} */
            state: "idle" | "running" | "waiting_peer" | "continuing" | "retiring" | "retired";
            item?: string | null;
            /** @description CALCULATED from observed_at. */
            elapsed_ms?: number | null;
            turns?: number;
            /** @description MEASURED (run.end reported). */
            tokens?: number | null;
            /** @description MEASURED (run.end cost_usd). */
            cost_cli_microusd?: number | null;
            /** @enum {string|null} */
            ring?: "closed" | "jagged" | "open" | "flat" | null;
        };
        MonitorSnapshot: {
            /** Format: date-time */
            observed_at: string;
            round?: number | null;
            figures: components["schemas"]["MonitorFigure"][];
            tiles: {
                id: string;
                role?: string | null;
                /** @enum {string} */
                shelf: "waiting" | "held" | "done" | "failed";
                holder?: string | null;
                parent?: string | null;
            }[];
            edges: {
                a: string;
                b: string;
                pi_permille?: number | null;
                messages: number;
            }[];
            meters: {
                tokens_total?: number | null;
                cost_cli_microusd?: number | null;
                budget_microusd?: number | null;
                budget_use_permille?: number | null;
            };
            mood: {
                /** @description events per minute */
                pace: number;
                collaboration: boolean;
                stall: boolean;
                tension: boolean;
                all_done: boolean;
            };
        };
        MonitorRecording: {
            /** Format: uuid */
            id: string;
            /** Format: date-time */
            started_at: string;
            /** Format: date-time */
            ended_at?: string | null;
            events: number;
            reader_version?: string;
        };
    };
    responses: {
        /** @description error */
        Error: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: {
        ws: string;
        job: string;
        budget: string;
        proposal: string;
        run: string;
        source: string;
        from: string;
        to: string;
        project: string;
        bucket: "hour" | "day" | "week";
        cursor: string;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    signup: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignupRequest"];
            };
        };
        responses: {
            /** @description created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenPair"];
                };
            };
            409: components["responses"]["Error"];
        };
    };
    login: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenPair"];
                };
            };
            401: components["responses"]["Error"];
        };
    };
    refresh: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenPair"];
                };
            };
            401: components["responses"]["Error"];
        };
    };
    logout: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description logged out */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    getMe: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["User"];
                };
            };
        };
    };
    listWorkspaces: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Workspace"][];
                };
            };
        };
    };
    createWorkspace: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkspaceCreate"];
            };
        };
        responses: {
            /** @description created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Workspace"];
                };
            };
        };
    };
    getWorkspace: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Workspace"];
                };
            };
            404: components["responses"]["Error"];
        };
    };
    listMembers: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Member"][];
                };
            };
        };
    };
    addMember: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MemberAdd"];
            };
        };
        responses: {
            /** @description added */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Member"];
                };
            };
        };
    };
    listProjects: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Project"][];
                };
            };
        };
    };
    createProject: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectCreate"];
            };
        };
        responses: {
            /** @description created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Project"];
                };
            };
        };
    };
    listSources: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Source"][];
                };
            };
        };
    };
    createSource: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceCreate"];
            };
        };
        responses: {
            /** @description created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Source"];
                };
            };
        };
    };
    createUpload: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": {
                    /** Format: uuid */
                    source_id: string;
                    declared_format?: components["schemas"]["SourceKind"];
                    file: string;
                };
            };
        };
        responses: {
            /** @description stored */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Upload"];
                };
            };
            413: components["responses"]["Error"];
        };
    };
    listIngestJobs: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IngestJob"][];
                };
            };
        };
    };
    getIngestJob: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                job: components["parameters"]["job"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IngestJob"];
                };
            };
        };
    };
    streamIngestJobEvents: {
        parameters: {
            query?: never;
            header?: {
                "Last-Event-ID"?: number;
            };
            path: {
                ws: components["parameters"]["ws"];
                job: components["parameters"]["job"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description event stream */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };
        };
    };
    listModels: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelWithPrice"][];
                };
            };
        };
    };
    usageSummary: {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UsageSummary"];
                };
            };
        };
    };
    tokenSeries: {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
                bucket?: components["parameters"]["bucket"];
                group_by?: "none" | "model" | "source_kind";
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SeriesSet"];
                };
            };
        };
    };
    callSizeHistogram: {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
                threshold?: number;
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Histogram"];
                };
            };
        };
    };
    compareConfigs: {
        parameters: {
            query: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
                dims: ("structure" | "model" | "context_mode" | "task_kind")[];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Comparison"];
                };
            };
        };
    };
    listCalls: {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                project?: components["parameters"]["project"];
                cursor?: components["parameters"]["cursor"];
                min_input?: number;
                model?: string;
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CallPage"];
                };
            };
        };
    };
    listSessions: {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionPage"];
                };
            };
        };
    };
    listTasks: {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                cursor?: components["parameters"]["cursor"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskPage"];
                };
            };
        };
    };
    updateTask: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                task: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TaskUpdate"];
            };
        };
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Task"];
                };
            };
        };
    };
    listBudgets: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Budget"][];
                };
            };
        };
    };
    createBudget: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BudgetCreate"];
            };
        };
        responses: {
            /** @description created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Budget"];
                };
            };
        };
    };
    getBudget: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                budget: components["parameters"]["budget"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Budget"];
                };
            };
        };
    };
    archiveBudget: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                budget: components["parameters"]["budget"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description archived */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    budgetBurn: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                budget: components["parameters"]["budget"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BurnSeries"];
                };
            };
        };
    };
    listBudgetAlerts: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BudgetAlert"][];
                };
            };
        };
    };
    listEstimates: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Estimate"][];
                };
            };
        };
    };
    createEstimate: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EstimateRequest"];
            };
        };
        responses: {
            /** @description created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Estimate"];
                };
            };
        };
    };
    getEstimate: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                estimate: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Estimate"];
                };
            };
        };
    };
    estimateAccuracy: {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Accuracy"];
                };
            };
        };
    };
    listAdvisorRules: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AdvisorRule"][];
                };
            };
        };
    };
    listFindings: {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Finding"][];
                };
            };
        };
    };
    listProposals: {
        parameters: {
            query?: {
                state?: components["schemas"]["ProposalState"];
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Proposal"][];
                };
            };
        };
    };
    getProposal: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                proposal: components["parameters"]["proposal"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Proposal"];
                };
            };
        };
    };
    decideProposal: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                proposal: components["parameters"]["proposal"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProposalDecision"];
            };
        };
        responses: {
            /** @description decided */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Proposal"];
                };
            };
            409: components["responses"]["Error"];
        };
    };
    createSimulation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationRequest"];
            };
        };
        responses: {
            /** @description created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Simulation"];
                };
            };
            422: components["responses"]["Error"];
        };
    };
    getSimulation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                simulation: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Simulation"];
                };
            };
        };
    };
    getProfile: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Profile"];
                };
            };
        };
    };
    putProfile: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Profile"];
            };
        };
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Profile"];
                };
            };
        };
    };
    getPersonalStats: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PersonalStat"][];
                };
            };
        };
    };
    listRecommendations: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Recommendation"][];
                };
            };
        };
    };
    listReports: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Report"][];
                };
            };
        };
    };
    generateReport: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Period"];
            };
        };
        responses: {
            /** @description created */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Report"];
                };
            };
        };
    };
    exportReport: {
        parameters: {
            query: {
                format: "json" | "csv";
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                report: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description file */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Report"];
                    "text/csv": string;
                };
            };
        };
    };
    listNotifications: {
        parameters: {
            query?: {
                unread?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Notification"][];
                };
            };
        };
    };
    markNotificationRead: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                notification: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description marked */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    getNotificationPrefs: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NotificationPref"][];
                };
            };
        };
    };
    putNotificationPrefs: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NotificationPref"][];
            };
        };
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NotificationPref"][];
                };
            };
        };
    };
    listAuditLog: {
        parameters: {
            query?: {
                from?: components["parameters"]["from"];
                to?: components["parameters"]["to"];
                cursor?: components["parameters"]["cursor"];
                action?: string;
            };
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditPage"];
                };
            };
        };
    };
    listIntegrations: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Integration"][];
                };
            };
        };
    };
    listProviderCredentials: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CredentialRef"][];
                };
            };
        };
    };
    storeProviderCredential: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CredentialCreate"];
            };
        };
        responses: {
            /** @description stored */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CredentialRef"];
                };
            };
        };
    };
    revokeProviderCredential: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                credential: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description revoked */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    listMonitorSources: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MonitorSource"][];
                };
            };
        };
    };
    registerMonitorSource: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    label: string;
                    path: string;
                };
            };
        };
        responses: {
            /** @description registered */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MonitorSource"];
                };
            };
        };
    };
    monitorSnapshot: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                source: components["parameters"]["source"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MonitorSnapshot"];
                };
            };
        };
    };
    streamMonitorEvents: {
        parameters: {
            query?: never;
            header?: {
                "Last-Event-ID"?: number;
            };
            path: {
                ws: components["parameters"]["ws"];
                source: components["parameters"]["source"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description event stream */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };
        };
    };
    listMonitorRecordings: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                source: components["parameters"]["source"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MonitorRecording"][];
                };
            };
        };
    };
    getMonitorRecording: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                source: components["parameters"]["source"];
                recording: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description recording */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/x-ndjson": string;
                };
            };
        };
    };
    listRuns: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Run"][];
                };
            };
        };
    };
    startRun: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    /** Format: uuid */
                    proposal_id: string;
                };
            };
        };
        responses: {
            /** @description started */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Run"];
                };
            };
        };
    };
    getRun: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Run"];
                };
            };
        };
    };
    streamRunEvents: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description event stream */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };
        };
    };
    runTimeline: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Timeline"];
                };
            };
        };
    };
    runFlow: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Funnel"];
                };
            };
        };
    };
    runNetwork: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Network"];
                };
            };
        };
    };
    runVerdicts: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                ws: components["parameters"]["ws"];
                run: components["parameters"]["run"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description ok */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Verdict"][];
                };
            };
        };
    };
}
