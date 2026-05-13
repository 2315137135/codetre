package main

import "fmt"

type Config struct {
    Port int
    Host string
}

type Server struct {
    config Config
}

func NewServer(cfg Config) *Server {
    return &Server{config: cfg}
}

func (s *Server) Listen() error {
    addr := fmt.Sprintf("%s:%d", s.config.Host, s.config.Port)
    fmt.Println("listening on", addr)
    return nil
}

func main() {
    cfg := Config{Port: 8080, Host: "localhost"}
    srv := NewServer(cfg)
    srv.Listen()
}
