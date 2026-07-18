package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const maxArtifactBytes = 512 << 20

type Client struct {
	baseURL    *url.URL
	apiKey     string
	httpClient *http.Client
	userAgent  string
}

type Error struct {
	StatusCode int
	Code       string
	Category   string
	Message    string
	Retryable  bool
	Details    map[string]any
}

func (e *Error) Error() string {
	if e.Code == "" {
		return fmt.Sprintf("Djass API returned HTTP %d: %s", e.StatusCode, e.Message)
	}
	return fmt.Sprintf("Djass API error %s (HTTP %d): %s", e.Code, e.StatusCode, e.Message)
}

type Project struct {
	ID            int            `json:"id"`
	Name          string         `json:"name"`
	Slug          string         `json:"slug"`
	Status        string         `json:"status"`
	ErrorMessage  string         `json:"error_message"`
	CreatedAt     string         `json:"created_at"`
	UpdatedAt     string         `json:"updated_at"`
	StartedAt     *string        `json:"started_at"`
	FinishedAt    *string        `json:"finished_at"`
	ArtifactReady bool           `json:"artifact_ready"`
	InputPayload  map[string]any `json:"input_payload"`
}

type ProjectCreateResponse struct {
	Project Project `json:"project"`
}

type ProjectList struct {
	Projects []Project      `json:"projects"`
	Total    int            `json:"total"`
	Limit    int            `json:"limit"`
	Offset   int            `json:"offset"`
	HasNext  bool           `json:"has_next"`
	Filters  map[string]any `json:"filters"`
}

type ProjectStatus struct {
	ID            int     `json:"id"`
	Status        string  `json:"status"`
	ErrorMessage  string  `json:"error_message"`
	ArtifactReady bool    `json:"artifact_ready"`
	StartedAt     *string `json:"started_at"`
	FinishedAt    *string `json:"finished_at"`
	UpdatedAt     string  `json:"updated_at"`
}

func NewClient(baseURL, apiKey string, httpClient *http.Client) (*Client, error) {
	parsed, err := url.Parse(strings.TrimRight(baseURL, "/"))
	if err != nil || parsed.Scheme == "" || parsed.Host == "" {
		return nil, fmt.Errorf("invalid Djass base URL %q", baseURL)
	}
	if parsed.Scheme != "https" && parsed.Scheme != "http" {
		return nil, fmt.Errorf("Djass base URL must use HTTP or HTTPS")
	}
	if parsed.Scheme != "https" && parsed.Hostname() != "localhost" && parsed.Hostname() != "127.0.0.1" {
		return nil, fmt.Errorf("Djass base URL must use HTTPS (HTTP is allowed only for localhost)")
	}
	if parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" {
		return nil, fmt.Errorf("Djass base URL cannot include credentials, a query string, or a fragment")
	}
	if httpClient == nil {
		httpClient = &http.Client{
			Timeout: 60 * time.Second,
			CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
				return errors.New("Djass API redirects are not allowed")
			},
		}
	}
	return &Client{baseURL: parsed, apiKey: apiKey, httpClient: httpClient, userAgent: "djass-cli/dev"}, nil
}

func (c *Client) SetUserAgent(userAgent string) {
	c.userAgent = userAgent
}

func (c *Client) Options(ctx context.Context) (json.RawMessage, error) {
	var result json.RawMessage
	err := c.doJSON(ctx, http.MethodGet, "/project-options", nil, &result)
	return result, err
}

func (c *Client) CreateProject(ctx context.Context, payload map[string]any) (ProjectCreateResponse, error) {
	var result ProjectCreateResponse
	err := c.doJSON(ctx, http.MethodPost, "/projects", payload, &result)
	return result, err
}

func (c *Client) ListProjects(ctx context.Context, limit, offset int, status string) (ProjectList, error) {
	query := url.Values{}
	query.Set("limit", strconv.Itoa(limit))
	query.Set("offset", strconv.Itoa(offset))
	if status != "" {
		query.Set("status", status)
	}
	var result ProjectList
	err := c.doJSON(ctx, http.MethodGet, "/projects?"+query.Encode(), nil, &result)
	return result, err
}

func (c *Client) GetProject(ctx context.Context, id int) (Project, error) {
	var result Project
	err := c.doJSON(ctx, http.MethodGet, fmt.Sprintf("/projects/%d", id), nil, &result)
	return result, err
}

func (c *Client) ProjectStatus(ctx context.Context, id int) (ProjectStatus, error) {
	var result ProjectStatus
	err := c.doJSON(ctx, http.MethodGet, fmt.Sprintf("/projects/%d/status", id), nil, &result)
	return result, err
}

func (c *Client) DownloadProject(ctx context.Context, id int, destination io.Writer) (int64, error) {
	request, err := c.newRequest(ctx, http.MethodGet, fmt.Sprintf("/projects/%d/download", id), nil)
	if err != nil {
		return 0, err
	}
	response, err := c.httpClient.Do(request)
	if err != nil {
		return 0, fmt.Errorf("download project artifact: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return 0, decodeError(response)
	}
	if response.ContentLength > maxArtifactBytes {
		return 0, fmt.Errorf("project artifact exceeds the %d MiB CLI safety limit", maxArtifactBytes>>20)
	}
	written, err := copyWithLimit(destination, response.Body, maxArtifactBytes)
	if err != nil {
		return written, fmt.Errorf("write project artifact: %w", err)
	}
	return written, nil
}

func copyWithLimit(destination io.Writer, source io.Reader, limit int64) (int64, error) {
	written, err := io.Copy(destination, io.LimitReader(source, limit+1))
	if err != nil {
		return written, err
	}
	if written > limit {
		return written, fmt.Errorf("project artifact exceeds the %d MiB CLI safety limit", maxArtifactBytes>>20)
	}
	return written, nil
}

func (c *Client) doJSON(ctx context.Context, method, path string, payload any, target any) error {
	var body io.Reader
	if payload != nil {
		encoded, err := json.Marshal(payload)
		if err != nil {
			return fmt.Errorf("encode request: %w", err)
		}
		body = bytes.NewReader(encoded)
	}
	request, err := c.newRequest(ctx, method, path, body)
	if err != nil {
		return err
	}
	if payload != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	response, err := c.httpClient.Do(request)
	if err != nil {
		return fmt.Errorf("call Djass API: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return decodeError(response)
	}
	if err := json.NewDecoder(response.Body).Decode(target); err != nil {
		return fmt.Errorf("decode Djass API response: %w", err)
	}
	return nil
}

func (c *Client) newRequest(ctx context.Context, method, path string, body io.Reader) (*http.Request, error) {
	endpoint := c.baseURL.String() + path
	request, err := http.NewRequestWithContext(ctx, method, endpoint, body)
	if err != nil {
		return nil, fmt.Errorf("build Djass API request: %w", err)
	}
	request.Header.Set("Accept", "application/json")
	request.Header.Set("User-Agent", c.userAgent)
	if c.apiKey != "" {
		request.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
	return request, nil
}

func decodeError(response *http.Response) error {
	var envelope struct {
		Error struct {
			Code      string         `json:"code"`
			Category  string         `json:"category"`
			Message   string         `json:"message"`
			Retryable bool           `json:"retryable"`
			Details   map[string]any `json:"details"`
		} `json:"error"`
	}
	data, _ := io.ReadAll(io.LimitReader(response.Body, 1<<20))
	_ = json.Unmarshal(data, &envelope)
	message := envelope.Error.Message
	if message == "" {
		message = strings.TrimSpace(string(data))
	}
	if message == "" {
		message = response.Status
	}
	return &Error{
		StatusCode: response.StatusCode,
		Code:       envelope.Error.Code,
		Category:   envelope.Error.Category,
		Message:    message,
		Retryable:  envelope.Error.Retryable,
		Details:    envelope.Error.Details,
	}
}
