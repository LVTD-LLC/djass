package command

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/LVTD-LLC/djass/cli/internal/api"
)

func TestProjectsCreateBuildsDynamicPayload(t *testing.T) {
	t.Setenv("DJASS_API_KEY", "secret")

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/v1/projects" {
			t.Fatalf("request = %s %s", r.Method, r.URL.Path)
		}
		var payload map[string]any
		if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
			t.Fatal(err)
		}
		if payload["project_name"] != "Agent App" || payload["project_slug"] != "agent_app" || payload["use_mcp"] != "y" {
			t.Fatalf("payload = %#v", payload)
		}
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"project":{"id":7,"name":"Agent App","slug":"agent_app","status":"queued","artifact_ready":false}}`))
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{
		"--base-url", server.URL + "/api/v1",
		"projects", "create",
		"--name", "Agent App",
		"--slug", "agent_app",
		"--set", "use_mcp=y",
	}, &stdout, &stderr)
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr.String())
	}
	if !strings.Contains(stdout.String(), `"id": 7`) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestGeneratePollsDownloadsAndExtracts(t *testing.T) {
	t.Setenv("DJASS_API_KEY", "secret")

	archive := zipBytes(t, map[string]string{"README.md": "generated"})
	var polls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/api/v1/projects":
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"project":{"id":9,"name":"Generated","slug":"generated","status":"queued","artifact_ready":false}}`))
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/projects/9/status":
			if polls.Add(1) == 1 {
				_, _ = w.Write([]byte(`{"id":9,"status":"generating","artifact_ready":false}`))
				return
			}
			_, _ = w.Write([]byte(`{"id":9,"status":"ready","artifact_ready":true}`))
		case r.Method == http.MethodGet && r.URL.Path == "/api/v1/projects/9/download":
			w.Header().Set("Content-Type", "application/zip")
			_, _ = w.Write(archive)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	destination := filepath.Join(t.TempDir(), "generated")
	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{
		"--base-url", server.URL + "/api/v1",
		"generate",
		"--name", "Generated",
		"--slug", "generated",
		"--output", destination,
		"--poll-interval", minimumPollInterval.String(),
		"--timeout", "2s",
	}, &stdout, &stderr)
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr.String())
	}
	content, err := os.ReadFile(filepath.Join(destination, "README.md"))
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != "generated" {
		t.Fatalf("content = %q", content)
	}
	if !strings.Contains(stdout.String(), `"project_id": 9`) || !strings.Contains(stdout.String(), `"output"`) {
		t.Fatalf("stdout = %s", stdout.String())
	}
}

func TestGenerateReportsFailedBuild(t *testing.T) {
	t.Setenv("DJASS_API_KEY", "secret")

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost {
			w.WriteHeader(http.StatusCreated)
			_, _ = w.Write([]byte(`{"project":{"id":11,"name":"Broken","slug":"broken","status":"queued","artifact_ready":false}}`))
			return
		}
		_, _ = w.Write([]byte(`{"id":11,"status":"failed","error_message":"template failed","artifact_ready":false}`))
	}))
	defer server.Close()

	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{
		"--base-url", server.URL,
		"generate", "--name", "Broken", "--slug", "broken",
		"--output", filepath.Join(t.TempDir(), "broken"),
		"--poll-interval", minimumPollInterval.String(), "--timeout", time.Second.String(),
	}, &stdout, &stderr)
	if exitCode == 0 || !strings.Contains(stderr.String(), "template failed") {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr.String())
	}
}

func TestProjectsDownloadAcceptsIDBeforeFlags(t *testing.T) {
	t.Setenv("DJASS_API_KEY", "secret")

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/projects/17/download" {
			t.Fatalf("path = %q", r.URL.Path)
		}
		_, _ = w.Write([]byte("zip-data"))
	}))
	defer server.Close()

	output := filepath.Join(t.TempDir(), "project.zip")
	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{
		"--base-url", server.URL + "/api/v1",
		"projects", "download", "17", "--output", output,
	}, &stdout, &stderr)
	if exitCode != 0 {
		t.Fatalf("exit = %d, stderr = %s", exitCode, stderr.String())
	}
	content, err := os.ReadFile(output)
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != "zip-data" {
		t.Fatalf("content = %q", content)
	}
}

func TestProjectsDownloadForcePreservesExistingFileWhenRequestFails(t *testing.T) {
	t.Setenv("DJASS_API_KEY", "secret")

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"error":{"code":"internal_error","category":"internal","message":"failed","retryable":false,"details":{}}}`))
	}))
	defer server.Close()

	output := filepath.Join(t.TempDir(), "project.zip")
	if err := os.WriteFile(output, []byte("keep-me"), 0o600); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{
		"--base-url", server.URL,
		"projects", "download", "17", "--output", output, "--force",
	}, &stdout, &stderr)
	if exitCode == 0 {
		t.Fatal("expected download failure")
	}
	content, err := os.ReadFile(output)
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != "keep-me" {
		t.Fatalf("existing content = %q", content)
	}
}

func TestVersionFlagDoesNotRequireACommand(t *testing.T) {
	t.Parallel()

	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{"--version"}, &stdout, &stderr)
	if exitCode != 0 || strings.TrimSpace(stdout.String()) != Version {
		t.Fatalf("exit = %d, stdout = %q, stderr = %q", exitCode, stdout.String(), stderr.String())
	}
}

func TestBuildPayloadRequiresStringProjectIdentity(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name    string
		payload string
	}{
		{name: "omitted name", payload: `{"project_slug":"agent_app"}`},
		{name: "omitted slug", payload: `{"project_name":"Agent App"}`},
		{name: "null name", payload: `{"project_name":null,"project_slug":"agent_app"}`},
		{name: "numeric slug", payload: `{"project_name":"Agent App","project_slug":42}`},
		{name: "blank name", payload: `{"project_name":"  ","project_slug":"agent_app"}`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "payload.json")
			if err := os.WriteFile(path, []byte(tt.payload), 0o600); err != nil {
				t.Fatal(err)
			}
			if _, err := buildPayload(path, "", "", nil); err == nil {
				t.Fatal("expected invalid project identity to be rejected")
			}
		})
	}
}

func TestBuildPayloadLimitsAndOverrides(t *testing.T) {
	t.Parallel()

	t.Run("rejects trailing JSON", func(t *testing.T) {
		path := filepath.Join(t.TempDir(), "payload.json")
		if err := os.WriteFile(path, []byte(`{"project_name":"One","project_slug":"one"} {"second":true}`), 0o600); err != nil {
			t.Fatal(err)
		}
		if _, err := buildPayload(path, "", "", nil); err == nil {
			t.Fatal("expected trailing JSON to be rejected")
		}
	})

	t.Run("rejects oversized file", func(t *testing.T) {
		path := filepath.Join(t.TempDir(), "payload.json")
		file, err := os.Create(path)
		if err != nil {
			t.Fatal(err)
		}
		if err := file.Truncate(maxPayloadBytes + 1); err != nil {
			t.Fatal(err)
		}
		if err := file.Close(); err != nil {
			t.Fatal(err)
		}
		if _, err := buildPayload(path, "", "", nil); err == nil {
			t.Fatal("expected oversized payload to be rejected")
		}
	})

	t.Run("flags override payload", func(t *testing.T) {
		path := filepath.Join(t.TempDir(), "payload.json")
		if err := os.WriteFile(path, []byte(`{"project_name":"Old","project_slug":"old","use_mcp":"n"}`), 0o600); err != nil {
			t.Fatal(err)
		}
		payload, err := buildPayload(path, "New", "new", []string{"use_mcp=y"})
		if err != nil {
			t.Fatal(err)
		}
		if payload["project_name"] != "New" || payload["project_slug"] != "new" || payload["use_mcp"] != "y" {
			t.Fatalf("payload = %#v", payload)
		}
	})
}

func TestWaitForProjectRequiresReadyArtifactAndTimesOut(t *testing.T) {
	t.Parallel()

	t.Run("ready without artifact keeps polling", func(t *testing.T) {
		var polls atomic.Int32
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			ready := polls.Add(1) > 1
			_ = json.NewEncoder(w).Encode(api.ProjectStatus{ID: 1, Status: "ready", ArtifactReady: ready})
		}))
		defer server.Close()
		client, err := api.NewClient(server.URL, "secret", server.Client())
		if err != nil {
			t.Fatal(err)
		}
		r := &runner{client: client}
		status, err := r.waitForProject(context.Background(), 1, time.Millisecond)
		if err != nil || !status.ArtifactReady || polls.Load() != 2 {
			t.Fatalf("status = %#v, polls = %d, err = %v", status, polls.Load(), err)
		}
	})

	t.Run("timeout", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			_ = json.NewEncoder(w).Encode(api.ProjectStatus{ID: 1, Status: "ready", ArtifactReady: false})
		}))
		defer server.Close()
		client, err := api.NewClient(server.URL, "secret", server.Client())
		if err != nil {
			t.Fatal(err)
		}
		r := &runner{client: client}
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Millisecond)
		defer cancel()
		if _, err := r.waitForProject(ctx, 1, time.Millisecond); err == nil {
			t.Fatal("expected polling timeout")
		}
	})
}

func TestLocalErrorsUseStructuredJSON(t *testing.T) {
	t.Setenv("DJASS_API_KEY", "test")

	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{"projects", "list", "--limit", "nope"}, &stdout, &stderr)
	if exitCode != exitUsage {
		t.Fatalf("exit = %d", exitCode)
	}
	var envelope struct {
		Error struct {
			Code     string         `json:"code"`
			Category string         `json:"category"`
			Details  map[string]any `json:"details"`
		} `json:"error"`
	}
	if err := json.Unmarshal(stderr.Bytes(), &envelope); err != nil {
		t.Fatalf("stderr is not JSON: %q: %v", stderr.String(), err)
	}
	if envelope.Error.Code != "usage_error" || envelope.Error.Category != "usage" || envelope.Error.Details["exit_code"] != float64(exitUsage) {
		t.Fatalf("error envelope = %#v", envelope)
	}
}

func TestGenerateRejectsAggressivePollingInterval(t *testing.T) {
	t.Setenv("DJASS_API_KEY", "test")

	var stdout, stderr bytes.Buffer
	exitCode := Run(context.Background(), []string{
		"generate", "--name", "Agent", "--slug", "agent",
		"--poll-interval", "1ms",
	}, &stdout, &stderr)
	if exitCode != exitUsage || !strings.Contains(stderr.String(), `"code":"usage_error"`) {
		t.Fatalf("exit = %d, stderr = %q", exitCode, stderr.String())
	}
}
