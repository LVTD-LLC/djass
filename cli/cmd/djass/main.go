package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"github.com/LVTD-LLC/djass/cli/internal/command"
)

var version = "dev"

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	command.Version = version
	os.Exit(command.Run(ctx, os.Args[1:], os.Stdout, os.Stderr))
}
