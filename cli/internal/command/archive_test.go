package command

import (
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func zipBytes(t *testing.T, files map[string]string) []byte {
	t.Helper()
	var buffer bytes.Buffer
	zw := zip.NewWriter(&buffer)
	for name, content := range files {
		entry, err := zw.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := entry.Write([]byte(content)); err != nil {
			t.Fatal(err)
		}
	}
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}
	return buffer.Bytes()
}

func TestExtractZIPRejectsPathTraversal(t *testing.T) {
	t.Parallel()

	destination := filepath.Join(t.TempDir(), "repo")
	err := extractZIP(zipBytes(t, map[string]string{"../escape.txt": "nope"}), destination)
	if err == nil {
		t.Fatal("expected path traversal error")
	}
	if _, statErr := os.Stat(filepath.Join(filepath.Dir(destination), "escape.txt")); !os.IsNotExist(statErr) {
		t.Fatalf("escape file exists: %v", statErr)
	}
}

func TestExtractZIPValidatesAllPathsBeforeWriting(t *testing.T) {
	t.Parallel()

	var buffer bytes.Buffer
	zw := zip.NewWriter(&buffer)
	regular, err := zw.Create("written-first.txt")
	if err != nil {
		t.Fatal(err)
	}
	_, _ = regular.Write([]byte("must not survive"))
	unsafe, err := zw.Create("../escape.txt")
	if err != nil {
		t.Fatal(err)
	}
	_, _ = unsafe.Write([]byte("nope"))
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}

	destination := filepath.Join(t.TempDir(), "repo")
	if err := extractZIP(buffer.Bytes(), destination); err == nil {
		t.Fatal("expected path traversal error")
	}
	if _, err := os.Stat(filepath.Join(destination, "written-first.txt")); !os.IsNotExist(err) {
		t.Fatalf("regular file was written before validation completed: %v", err)
	}
}

func TestExtractZIPWritesRegularFiles(t *testing.T) {
	t.Parallel()

	destination := filepath.Join(t.TempDir(), "repo")
	err := extractZIP(zipBytes(t, map[string]string{"README.md": "hello", "app/main.py": "print('ok')"}), destination)
	if err != nil {
		t.Fatal(err)
	}
	content, err := os.ReadFile(filepath.Join(destination, "app", "main.py"))
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != "print('ok')" {
		t.Fatalf("content = %q", content)
	}
}

func TestExtractZIPRejectsNonRegularEntries(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		mode os.FileMode
	}{
		{name: "symlink", mode: os.ModeSymlink | 0o777},
		{name: "device", mode: os.ModeDevice | 0o600},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var buffer bytes.Buffer
			writer := zip.NewWriter(&buffer)
			header := &zip.FileHeader{Name: tt.name}
			header.SetMode(tt.mode)
			if _, err := writer.CreateHeader(header); err != nil {
				t.Fatal(err)
			}
			if err := writer.Close(); err != nil {
				t.Fatal(err)
			}
			if err := extractZIP(buffer.Bytes(), filepath.Join(t.TempDir(), "repo")); err == nil {
				t.Fatalf("expected %s entry to be rejected", tt.name)
			}
		})
	}
}

func TestExtractZIPRejectsDeclaredOversizeEntry(t *testing.T) {
	t.Parallel()

	file := &zip.File{FileHeader: zip.FileHeader{Name: "huge.bin", UncompressedSize64: maxExtractedBytes + 1}}
	reader := &zip.Reader{File: []*zip.File{file}}
	if err := extractZIPReader(reader, filepath.Join(t.TempDir(), "repo")); err == nil {
		t.Fatal("expected declared oversize entry to be rejected")
	}
}

func TestEnsureEmptyDestinationRefusesExistingContent(t *testing.T) {
	t.Parallel()

	destination := t.TempDir()
	if err := os.WriteFile(filepath.Join(destination, "keep.txt"), []byte("important"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := ensureEmptyDestination(destination); err == nil {
		t.Fatal("expected non-empty destination error")
	}
}

func TestExtractZIPRejectsSymlinkDestination(t *testing.T) {
	t.Parallel()

	parent := t.TempDir()
	target := filepath.Join(parent, "target")
	if err := os.Mkdir(target, 0o755); err != nil {
		t.Fatal(err)
	}
	destination := filepath.Join(parent, "repo")
	if err := os.Symlink(target, destination); err != nil {
		t.Skipf("symlinks are unavailable: %v", err)
	}
	if err := extractZIP(zipBytes(t, map[string]string{"README.md": "nope"}), destination); err == nil {
		t.Fatal("expected symlink destination to be rejected")
	}
	if _, err := os.Stat(filepath.Join(target, "README.md")); !os.IsNotExist(err) {
		t.Fatalf("file escaped through symlink destination: %v", err)
	}
}

func TestExtractZIPFileAtomicCleansPartialOutput(t *testing.T) {
	t.Parallel()

	var buffer bytes.Buffer
	writer := zip.NewWriter(&buffer)
	for _, entry := range []struct{ name, content string }{{"first.txt", "first-content"}, {"second.txt", "second-content"}} {
		header := &zip.FileHeader{Name: entry.name, Method: zip.Store}
		file, err := writer.CreateHeader(header)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := file.Write([]byte(entry.content)); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	corrupt := buffer.Bytes()
	index := bytes.Index(corrupt, []byte("second-content"))
	if index < 0 {
		t.Fatal("could not locate stored entry")
	}
	corrupt[index] ^= 0xff
	archive := filepath.Join(t.TempDir(), "project.zip")
	if err := os.WriteFile(archive, corrupt, 0o600); err != nil {
		t.Fatal(err)
	}
	destination := filepath.Join(t.TempDir(), "repo")
	if err := extractZIPFileAtomic(archive, destination); err == nil {
		t.Fatal("expected corrupt archive to fail")
	}
	if _, err := os.Stat(destination); !os.IsNotExist(err) {
		t.Fatalf("partial destination remains: %v", err)
	}
}

func TestExtractZIPRejectsExcessiveEntryCount(t *testing.T) {
	t.Parallel()

	reader := &zip.Reader{File: make([]*zip.File, maxArchiveEntries+1)}
	if err := extractZIPReader(reader, filepath.Join(t.TempDir(), "repo")); err == nil {
		t.Fatal("expected excessive entry count to be rejected")
	}
}
