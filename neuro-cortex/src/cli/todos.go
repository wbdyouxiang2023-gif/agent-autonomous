package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

type Todo struct {
	ID        int    `json:"id"`
	Text      string `json:"text"`
	Done      bool   `json:"done"`
	CreatedAt string `json:"created_at"`
}

type Store struct {
	Path   string   `json:"path"`
	Todos  []Todo   `json:"todos"`
	NextID int      `json:"next_id"`
}

func (s *Store) Load() error {
	data, err := os.ReadFile(s.Path)
	if err != nil {
		if os.IsNotExist(err) {
			s.NextID = 1
			return nil
		}
		return err
	}
	json.Unmarshal(data, s)
	if s.NextID == 0 { s.NextID = 1 }
	return nil
}

func (s *Store) Save() error {
	dir := filepath.Dir(s.Path)
	os.MkdirAll(dir, 0755)
	data, _ := json.MarshalIndent(s, "", "  ")
	return os.WriteFile(s.Path, data, 0644)
}

func main() {
	store := &Store{Path: filepath.Join(os.Getenv("HOME"), ".todos.json")}
	store.Load()
	if len(os.Args) < 2 { store.List(); return }
	switch os.Args[1] {
	case "add":
		store.Add(os.Args[2])
		store.Save()
		fmt.Printf("Added #%d: %s\n", store.NextID-1, os.Args[2])
	case "list":
		store.List()
	case "done":
		id := 1
		fmt.Sscanf(os.Args[2], "%d", &id)
		store.Done(id)
		store.Save()
	}
}

func (s *Store) List() {
	for _, t := range s.Todos {
		fmt.Printf("[%s] %d: %s\n", map[bool]string{true:"x",false:" "}[t.Done], t.ID, t.Text)
	}
}

func (s *Store) Add(text string) {
	s.Todos = append(s.Todos, Todo{ID: s.NextID, Text: text, Done: false, CreatedAt: time.Now().Format("2006-01-02 15:04")})
	s.NextID++
}

func (s *Store) Done(id int) {
	for i := range s.Todos {
		if s.Todos[i].ID == id { s.Todos[i].Done = true }
	}
}
