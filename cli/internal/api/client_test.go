package api

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestClientSendsBearerAuthenticationAndDecodesProject(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer secret" {
			t.Fatalf("Authorization = %q", got)
		}
		if r.URL.Path != "/api/v1/projects/42" {
			t.Fatalf("path = %q", r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(Project{ID: 42, Name: "Agent App", Status: "ready"})
	}))
	defer server.Close()

	client, err := NewClient(server.URL+"/api/v1", "secret", server.Client())
	if err != nil {
		t.Fatal(err)
	}
	project, err := client.GetProject(context.Background(), 42)
	if err != nil {
		t.Fatal(err)
	}
	if project.ID != 42 || project.Status != "ready" {
		t.Fatalf("project = %#v", project)
	}
}

func TestOptionsAndListProjectsRequestContract(t *testing.T) {
	t.Parallel()

	var requests int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		switch requests {
		case 1:
			if r.Method != http.MethodGet || r.URL.Path != "/api/v1/project-options" {
				t.Fatalf("options request = %s %s", r.Method, r.URL.Path)
			}
			_, _ = w.Write([]byte(`{"options":{}}`))
		case 2:
			if r.Method != http.MethodGet || r.URL.Path != "/api/v1/projects" {
				t.Fatalf("list request = %s %s", r.Method, r.URL.Path)
			}
			if got := r.URL.Query(); got.Get("limit") != "25" || got.Get("offset") != "5" || got.Get("status") != "ready" {
				t.Fatalf("list query = %v", got)
			}
			_, _ = w.Write([]byte(`{"projects":[],"total":0,"limit":25,"offset":5,"has_next":false}`))
		}
	}))
	defer server.Close()

	client, err := NewClient(server.URL+"/api/v1", "secret", server.Client())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.Options(context.Background()); err != nil {
		t.Fatal(err)
	}
	list, err := client.ListProjects(context.Background(), 25, 5, "ready")
	if err != nil {
		t.Fatal(err)
	}
	if list.Limit != 25 || list.Offset != 5 {
		t.Fatalf("list = %#v", list)
	}
}

func TestDownloadProjectRejectsDeclaredOversizeArtifact(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Length", "536870913")
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()
	client, err := NewClient(server.URL, "secret", server.Client())
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.DownloadProject(context.Background(), 1, &bytes.Buffer{}); err == nil {
		t.Fatal("expected declared oversize artifact to be rejected")
	}
}

func TestCopyWithLimitRejectsUnknownLengthOverflow(t *testing.T) {
	t.Parallel()

	var destination bytes.Buffer
	written, err := copyWithLimit(&destination, bytes.NewBufferString("12345"), 4)
	if err == nil || written != 5 {
		t.Fatalf("written = %d, err = %v", written, err)
	}
}

func TestNewClientRejectsAmbiguousOrUnsafeBaseURLs(t *testing.T) {
	t.Parallel()

	for _, baseURL := range []string{
		"ftp://localhost/api/v1",
		"http://example.com/api/v1",
		"https://user:pass@example.com/api/v1",
		"https://example.com/api/v1?tenant=other",
		"https://example.com/api/v1#fragment",
	} {
		t.Run(baseURL, func(t *testing.T) {
			if _, err := NewClient(baseURL, "secret", nil); err == nil {
				t.Fatalf("expected %q to be rejected", baseURL)
			}
		})
	}
}

func TestClientReturnsStructuredAPIError(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusForbidden)
		_, _ = w.Write([]byte(`{"error":{"code":"insufficient_scope","category":"auth","message":"missing scope","retryable":false,"details":{"required_scope":"projects:read"}}}`))
	}))
	defer server.Close()

	client, err := NewClient(server.URL, "secret", server.Client())
	if err != nil {
		t.Fatal(err)
	}
	_, err = client.GetProject(context.Background(), 42)
	apiErr, ok := err.(*Error)
	if !ok {
		t.Fatalf("error type = %T, want *Error", err)
	}
	if apiErr.StatusCode != http.StatusForbidden || apiErr.Code != "insufficient_scope" || apiErr.Retryable {
		t.Fatalf("error = %#v", apiErr)
	}
}
