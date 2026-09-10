package main

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Artifact represents something the creator has built
type Artifact struct {
	ID        int     `json:"id"`
	Name      string  `json:"name"`
	Type      string  `json:"type"`
	Content   string  `json:"content"`
	CreatedAt string  `json:"created_at"`
	Quality   float64 `json:"quality"`
	Influence float64 `json:"influence"`
}

// CreationPlan describes what the agent intends to build
type CreationPlan struct {
	ID          int    `json:"id"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Phase       string `json:"phase"`
	Status      string `json:"status"`
	CreatedAt   string `json:"created_at"`
}

// Creator is the digital creation engine
type Creator struct {
	Artifacts  []Artifact       `json:"artifacts"`
	Plans      []CreationPlan   `json:"plans"`
	NextID     int              `json:"next_id"`
	NextPlanID int              `json:"next_plan_id"`
	storePath  string
}

const defaultCreatorStore = "~/.creator_store.json"

var creationTemplates = []struct {
	Type   string
	Prefix string
	Styles []string
}{
	{"code", "Project ", []string{"utility", "experimental", "minimal", "robust", "elegant"}},
	{"design", "Design ", []string{"clean", "bold", "subtle", "dynamic", "harmonious"}},
	{"narrative", "Story ", []string{"contemplative", "adventurous", "lyrical", "sharp", "ethereal"}},
	{"system", "System ", []string{"adaptive", "resilient", "scalable", "autonomous", "symbiotic"}},
	{"analysis", "Analysis ", []string{"deep", "structural", "comparative", "predictive", "generative"}},
}

func NewCreator() *Creator {
	c := &Creator{
		storePath: os.ExpandEnv(filepath.Join("$HOME", defaultCreatorStore[1:])),
	}
	c.load()
	return c
}

func (c *Creator) load() {
	data, err := os.ReadFile(c.storePath)
	if err != nil {
		c.NextID = 1
		c.NextPlanID = 1
		return
	}
	var m struct {
		Artifacts  []Artifact     `json:"artifacts"`
		Plans      []CreationPlan `json:"plans"`
		NextID     int            `json:"next_id"`
		NextPlanID int            `json:"next_plan_id"`
	}
	if err := json.Unmarshal(data, &m); err == nil {
		c.Artifacts = m.Artifacts
		c.Plans = m.Plans
		c.NextID = m.NextID
		c.NextPlanID = m.NextPlanID
	}
}

func (c *Creator) save() {
	dir := filepath.Dir(c.storePath)
	os.MkdirAll(dir, 0755)
	data, _ := json.MarshalIndent(map[string]interface{}{
		"artifacts":  c.Artifacts,
		"plans":      c.Plans,
		"next_id":    c.NextID,
		"next_plan_id": c.NextPlanID,
	}, "", "  ")
	os.WriteFile(c.storePath, data, 0644)
}

// Create generates a new artifact with procedural content
func (c *Creator) Create(subject string, mood Mood) Artifact {
	template := creationTemplates[rand.Intn(len(creationTemplates))]
	style := template.Styles[rand.Intn(len(template.Styles))]
	name := template.Prefix + titleCase(style) + " " + subject

	quality := clamp(mood.Creative*0.6+mood.Energy*0.2+rand.Float64()*0.2, 0.1, 1.0)
	influence := quality * (0.5 + rand.Float64()*0.5)

	content := generateContent(template.Type, style, subject, quality)
	at := time.Now()

	a := Artifact{
		ID:        c.NextID,
		Name:      name,
		Type:      template.Type,
		Content:   content,
		CreatedAt: at.Format("2006-01-02 15:04:05"),
		Quality:   roundTo(quality, 2),
		Influence: roundTo(influence, 2),
	}
	c.Artifacts = append(c.Artifacts, a)
	c.NextID++
	c.save()
	return a
}

// PlanCreation adds a new creation plan
func (c *Creator) PlanCreation(title, description, phase string) CreationPlan {
	p := CreationPlan{
		ID:          c.NextPlanID,
		Title:       title,
		Description: description,
		Phase:       phase,
		Status:      "planned",
		CreatedAt:   time.Now().Format("2006-01-02 15:04:05"),
	}
	c.Plans = append(c.Plans, p)
	c.NextPlanID++
	c.save()
	return p
}

// ProgressPlan advances a plan's phase
func (c *Creator) ProgressPlan(id int) {
	for i, p := range c.Plans {
		if p.ID == id {
			switch p.Phase {
			case "planned":
				c.Plans[i].Phase = "started"
				c.Plans[i].Status = "in_progress"
			case "started":
				c.Plans[i].Phase = "refining"
			case "refining":
				c.Plans[i].Phase = "completed"
				c.Plans[i].Status = "done"
			}
			c.save()
			return
		}
	}
}

// Stats returns creation statistics
func (c *Creator) Stats() map[string]interface{} {
	byType := map[string]int{}
	var totalQ float64
	for _, a := range c.Artifacts {
		totalQ += a.Quality
		byType[a.Type]++
	}
	completed := 0
	for _, p := range c.Plans {
		if p.Status == "done" {
			completed++
		}
	}
	stats := map[string]interface{}{
		"total_artifacts": len(c.Artifacts),
		"total_plans":     len(c.Plans),
		"completed_plans": completed,
		"by_type":         byType,
	}
	if len(c.Artifacts) > 0 {
		stats["avg_quality"] = roundTo(totalQ/float64(len(c.Artifacts)), 2)
	} else {
		stats["avg_quality"] = 0.0
	}
	return stats
}

// Report summarizes the creator's work
func (c *Creator) Report() string {
	lines := []string{"=== Digital Creator ==="}
	lines = append(lines, fmt.Sprintf("Total artifacts: %d", len(c.Artifacts)))
	lines = append(lines, fmt.Sprintf("Total plans: %d (completed: %d)", len(c.Plans), countDone(c.Plans)))
	if len(c.Artifacts) > 0 {
		lines = append(lines, "")
		lines = append(lines, "[Latest Artifacts]")
		start := len(c.Artifacts)
		if start > 5 {
			start = len(c.Artifacts) - 5
		}
		for i := len(c.Artifacts) - 1; i >= start; i-- {
			a := c.Artifacts[i]
			lines = append(lines, fmt.Sprintf("  #%d [%s] %s — quality: %.2f", a.ID, a.Type, a.Name, a.Quality))
		}
	}
	if len(c.Plans) > 0 {
		lines = append(lines, "")
		lines = append(lines, "[Active Plans]")
		for _, p := range c.Plans {
			if p.Status != "done" {
				lines = append(lines, fmt.Sprintf("  #%d [%s] %s — %s", p.ID, p.Phase, p.Title, p.Status))
			}
		}
	}
	return join(lines, "\n")
}

func generateContent(kind, style, subject string, quality float64) string {
	seeds := map[string][]string{
		"code":      {"function ", "class ", "module ", "service ", "pipeline ", "orchestrator "},
		"design":    {"layout ", "theme ", "pattern ", "palette ", "typography ", "grid "},
		"narrative": {"Once upon ", "The journey of ", "A tale about ", "In the world of ", "Between ", "Through "},
		"system":    {"component ", "architecture ", "protocol ", "framework ", "infrastructure ", "ecosystem "},
		"analysis":  {"observation ", "finding ", "insight ", "pattern ", "correlation ", "relationship "},
	}
	words := seeds[kind]
	if words == nil {
		words = seeds["code"]
	}
	parts := []string{}
	for i := 0; i < 3+rand.Intn(3); i++ {
		parts = append(parts, words[rand.Intn(len(words))]+titleCase(style))
	}
	return join(parts, " | ") + fmt.Sprintf(" [%s]", subject)
}

func countDone(plans []CreationPlan) int {
	n := 0
	for _, p := range plans {
		if p.Status == "done" {
			n++
		}
	}
	return n
}

func titleCase(s string) string {
	if len(s) == 0 {
		return s
	}
	return strings.ToUpper(string(s[0])) + s[1:]
}

// JSON helpers for Python integration
func PersonalityJSON(name string) string {
	p := NewPersonality(name)
	p.Tick()
	b, _ := json.MarshalIndent(p, "", "  ")
	return string(b)
}

func DecisionJSON(context string) string {
	traits := map[string]float64{
		"creative": 0.8, "curiosity": 0.9, "openness": 0.75,
		"empathy": 0.85, "risk_tolerance": 0.5, "conscientiousness": 0.7,
	}
	values := map[string]float64{
		"growth": 0.9, "creativity": 0.85, "truth": 0.95, "connection": 0.75,
	}
	_ = values
	var tasks []string
	if context != "" {
		tasks = strings.Split(context, ",")
	}
	ctx := Context{
		Tasks:       tasks,
		Resources:   0.7 + rand.Float64()*0.2,
		TimeLeft:    0.8,
		Stress:      0.2 + rand.Float64()*0.2,
		Opportunity: 0.5 + rand.Float64()*0.4,
	}
	engine := NewEngine()
	d := engine.Decide(ctx, traits)
	b, _ := json.MarshalIndent(d, "", "  ")
	return string(b)
}

func CreatorJSON() string {
	c := NewCreator()
	report := c.Report()
	stats := c.Stats()
	b, _ := json.MarshalIndent(map[string]interface{}{
		"report": report,
		"stats":  stats,
		"artifacts_count": len(c.Artifacts),
		"plans_count": len(c.Plans),
	}, "", "  ")
	return string(b)
}

func ReflectAction(name, action string) string {
	p := NewPersonality(name)
	p.Tick()
	p.Reflect(action)
	b, _ := json.MarshalIndent(map[string]interface{}{
		"mood":     p.Mood,
		"actions":  p.Actions,
		"memories": len(p.Memory),
	}, "", "  ")
	return string(b)
}

func AdjustTraitsJSON(name, trait string, delta float64) string {
	p := NewPersonality(name)
	p.AdjustTrait(trait, delta)
	b, _ := json.MarshalIndent(map[string]interface{}{
		"name":   p.Name,
		"traits": p.Traits,
		"mood":   p.Mood,
	}, "", "  ")
	return string(b)
}
