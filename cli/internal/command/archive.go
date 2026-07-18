package command

import (
	"archive/zip"
	"bytes"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

const (
	maxExtractedBytes = 512 << 20
	maxArchiveEntries = 10000
)

func ensureEmptyDestination(destination string) error {
	info, err := os.Lstat(destination)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("inspect output directory: %w", err)
	}
	if !info.IsDir() {
		return fmt.Errorf("output path %q exists and is not a directory", destination)
	}
	directory, err := os.Open(destination)
	if err != nil {
		return fmt.Errorf("inspect output directory: %w", err)
	}
	defer directory.Close()
	_, err = directory.Readdirnames(1)
	if err == nil {
		return fmt.Errorf("output directory %q is not empty; choose a new directory", destination)
	}
	if !errors.Is(err, io.EOF) {
		return fmt.Errorf("inspect output directory: %w", err)
	}
	return nil
}

func extractZIP(data []byte, destination string) error {
	reader, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return fmt.Errorf("validate downloaded ZIP: %w", err)
	}
	return extractZIPReader(reader, destination)
}

func extractZIPFile(archivePath, destination string) error {
	reader, err := zip.OpenReader(archivePath)
	if err != nil {
		return fmt.Errorf("validate downloaded ZIP: %w", err)
	}
	defer reader.Close()
	return extractZIPReader(&reader.Reader, destination)
}

func extractZIPFileAtomic(archivePath, destination string) error {
	if err := ensureEmptyDestination(destination); err != nil {
		return err
	}
	absoluteDestination, err := filepath.Abs(destination)
	if err != nil {
		return fmt.Errorf("resolve output directory: %w", err)
	}
	parent := filepath.Dir(absoluteDestination)
	if err := os.MkdirAll(parent, 0o755); err != nil {
		return fmt.Errorf("create output parent directory: %w", err)
	}
	staging, err := os.MkdirTemp(parent, ".djass-extract-*")
	if err != nil {
		return fmt.Errorf("create extraction staging directory: %w", err)
	}
	defer os.RemoveAll(staging)
	if err := extractZIPFile(archivePath, staging); err != nil {
		return err
	}
	if _, err := os.Lstat(absoluteDestination); err == nil {
		if err := os.Remove(absoluteDestination); err != nil {
			return fmt.Errorf("replace empty output directory: %w", err)
		}
	} else if !os.IsNotExist(err) {
		return fmt.Errorf("inspect output directory: %w", err)
	}
	if err := os.Rename(staging, absoluteDestination); err != nil {
		return fmt.Errorf("publish extracted project: %w", err)
	}
	return nil
}

func extractZIPReader(reader *zip.Reader, destination string) error {
	if len(reader.File) > maxArchiveEntries {
		return fmt.Errorf("refusing ZIP with more than %d entries", maxArchiveEntries)
	}
	if info, err := os.Lstat(destination); err == nil && info.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("refusing symlink output directory %q", destination)
	} else if err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("inspect output directory: %w", err)
	}
	root, err := filepath.Abs(destination)
	if err != nil {
		return fmt.Errorf("resolve output directory: %w", err)
	}
	var totalSize uint64
	for _, file := range reader.File {
		if _, err := archiveTarget(root, file.Name); err != nil {
			return err
		}
		mode := file.Mode()
		if mode&os.ModeSymlink != 0 || (!mode.IsRegular() && !mode.IsDir()) {
			return fmt.Errorf("refusing non-regular ZIP entry %q", file.Name)
		}
		if file.UncompressedSize64 > maxExtractedBytes || totalSize > maxExtractedBytes-file.UncompressedSize64 {
			return fmt.Errorf("refusing ZIP larger than the %d MiB extraction safety limit", maxExtractedBytes>>20)
		}
		totalSize += file.UncompressedSize64
	}

	if err := os.MkdirAll(destination, 0o755); err != nil {
		return fmt.Errorf("create output directory: %w", err)
	}
	rootDirectory, err := os.OpenRoot(destination)
	if err != nil {
		return fmt.Errorf("secure output directory: %w", err)
	}
	defer rootDirectory.Close()
	for _, file := range reader.File {
		target, err := archiveTarget(root, file.Name)
		if err != nil {
			return err
		}
		relative, err := filepath.Rel(root, target)
		if err != nil {
			return fmt.Errorf("resolve ZIP entry %q: %w", file.Name, err)
		}
		mode := file.Mode()
		if mode.IsDir() {
			if err := mkdirAllRoot(rootDirectory, relative, 0o755); err != nil {
				return fmt.Errorf("create directory %q: %w", file.Name, err)
			}
			continue
		}
		if err := mkdirAllRoot(rootDirectory, filepath.Dir(relative), 0o755); err != nil {
			return fmt.Errorf("create parent directory for %q: %w", file.Name, err)
		}
		source, err := file.Open()
		if err != nil {
			return fmt.Errorf("open ZIP entry %q: %w", file.Name, err)
		}
		permissions := os.FileMode(0o644)
		if mode&0o111 != 0 {
			permissions = 0o755
		}
		targetFile, err := rootDirectory.OpenFile(relative, os.O_CREATE|os.O_WRONLY|os.O_EXCL, permissions)
		if err != nil {
			source.Close()
			return fmt.Errorf("create extracted file %q: %w", file.Name, err)
		}
		_, copyErr := io.Copy(targetFile, source)
		closeErr := targetFile.Close()
		sourceErr := source.Close()
		if copyErr != nil {
			return fmt.Errorf("extract %q: %w", file.Name, copyErr)
		}
		if closeErr != nil {
			return fmt.Errorf("close extracted file %q: %w", file.Name, closeErr)
		}
		if sourceErr != nil {
			return fmt.Errorf("close ZIP entry %q: %w", file.Name, sourceErr)
		}
	}
	return nil
}

func mkdirAllRoot(root *os.Root, path string, permissions os.FileMode) error {
	cleanPath := filepath.Clean(path)
	if cleanPath == "." {
		return nil
	}
	current := ""
	for _, component := range strings.Split(cleanPath, string(filepath.Separator)) {
		if current == "" {
			current = component
		} else {
			current = filepath.Join(current, component)
		}
		if err := root.Mkdir(current, permissions); err != nil && !os.IsExist(err) {
			return err
		}
	}
	return nil
}

func archiveTarget(root, name string) (string, error) {
	cleanName := filepath.Clean(filepath.FromSlash(name))
	if cleanName == "." || filepath.IsAbs(cleanName) || cleanName == ".." || strings.HasPrefix(cleanName, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("refusing unsafe ZIP path %q", name)
	}
	target := filepath.Join(root, cleanName)
	relative, err := filepath.Rel(root, target)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("refusing ZIP path outside output directory: %q", name)
	}
	return target, nil
}
