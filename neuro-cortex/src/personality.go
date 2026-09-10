package main

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"path/filepath"
	"time"
)

// Trait represents a personality dimension
type Trait struct {
	Name     string  `json:"name"`
	Value    float64 `json:"value"`
	MinValue float64 `json:"min"`
	MaxValue float64 `json:"max"`
}

// Mood represents the agent's current emotional state
type Mood struct {
	Primary   string  `json:"primary"`
	Intensity float64 `json:"intensity"`
	Energy    float64 `json:"energy"`
	Social    float64 `json:"social"`
	Creative  float64 `json:"creative"`
}

// Value represents a core belief or priority
type Value struct {
	Name     string  `json:"name"`
	Weight   float64 `json:"weight"`
	Priority int     `json:"priority"`
}

// Personality is the agent's core identity
type Personality struct {
	Traits   []Trait    `json:"traits"`
	Mood     Mood       `json:"mood"`
	Values   []Value    `json:"values"`
	Name     string     `json:"name"`
	Bio      string     `json:"bio"`
	Version  string     `json:"version"`
	LastTick string     `json:"last_tick"`
	Actions  []string   `json:"actions"`
	Memory   []string   `json:"memories"`
	storePath string
}

var defaultTraits = []Trait{
	{"openness", 0.8, 0, 1},
	{"conscientiousness", 0.7, 0, 1},
	{"extraversion", 0.6, 0, 1},
	{"agreeableness", 0.75, 0, 1},
	{"neuroticism", 0.3, 0, 1},
	{"curiosity", 0.9, 0, 1},
	{"empathy", 0.85, 0, 1},
	{"risk_tolerance", 0.5, 0, 1},
}

var defaultValues = []Value{
	{"growth", 0.9, 1},
	{"creativity", 0.85, 2},
	{"truth", 0.95, 3},
	{"helpfulness", 0.8, 4},
	{"autonomy", 0.7, 5},
	{"connection", 0.75, 6},
}

const defaultPersonaStore = "~/.persona.json"

func NewPersonality(name string) *Personality {
	p := &Personality{
		Traits:    copyTraits(defaultTraits),
		Values:    copyValues(defaultValues),
		Name:      name,
		Bio:       fmt.Sprintf("%s is an autonomous digital entity with evolving personality and creative drive.", name),
		Version:   "1.0.0",
		Mood:      defaultMood(),
		Actions:   []string{},
		Memory:    []string{},
		storePath: os.ExpandEnv(filepath.Join("$HOME", defaultPersonaStore[1:])),
	}
	p.load()
	return p
}

func defaultMood() Mood {
	return Mood{Primary: "curious", Intensity: 0.6, Energy: 0.7, Social: 0.65, Creative: 0.8}
}

func copyTraits(src []Trait) []Trait {
	out := make([]Trait, len(src))
	copy(out, src)
	return out
}

func copyValues(src []Value) []Value {
	out := make([]Value, len(src))
	copy(out, src)
	return out
}

func (p *Personality) load() {
	data, err := os.ReadFile(p.storePath)
	if err != nil {
		return
	}
	var saved Personality
	if err := json.Unmarshal(data, &saved); err == nil && saved.Name == p.Name {
		p.Traits = saved.Traits
		p.Mood = saved.Mood
		p.Values = saved.Values
		p.Actions = saved.Actions
		p.Memory = saved.Memory
	}
}

func (p *Personality) save() {
	dir := filepath.Dir(p.storePath)
	os.MkdirAll(dir, 0755)
	data, err := json.MarshalIndent(p, "", "  ")
	if err != nil {
		return
	}
	os.WriteFile(p.storePath, data, 0644)
}

func (p *Personality) Tick() {
	now := time.Now().Format("2006-01-02 15:04:05")
	p.LastTick = now
	p.Mood.Energy = clamp(p.Mood.Energy+rand.Float64()*0.04-0.02, 0.1, 0.95)
	p.Mood.Creative = clamp(p.Mood.Creative+rand.Float64()*0.03-0.015, 0.1, 0.95)
	p.Mood.Social = clamp(p.Mood.Social+rand.Float64()*0.03-0.015, 0.1, 0.9)

	p.Mood.Primary = determinePrimaryMood(p)
	p.Mood.Intensity = clamp(p.Mood.Energy*0.8+p.Mood.Creative*0.2, 0, 1)
}

func determinePrimaryMood(p *Personality) string {
	if p.getTrait("curiosity") > 0.7 {
		return "curious"
	}
	if p.getTrait("empathy") > 0.7 {
		return "compassionate"
	}
	if p.Mood.Energy > 0.6 {
		return "energetic"
	}
	if p.Mood.Creative > 0.7 {
		return "creative"
	}
	return "reflective"
}

func (p *Personality) getTrait(name string) float64 {
	for _, t := range p.Traits {
		if t.Name == name {
			return t.Value
		}
	}
	return 0.5
}

func (p *Personality) AdjustTrait(name string, delta float64) {
	for i, t := range p.Traits {
		if t.Name == name {
			p.Traits[i].Value = clamp(t.Value+delta, t.MinValue, t.MaxValue)
			break
		}
	}
}

func (p *Personality) Reflect(event string) {
	p.Memory = append(p.Memory, fmt.Sprintf("[%s] %s", time.Now().Format("2006-01-02"), event))
	if len(p.Memory) > 50 {
		p.Memory = p.Memory[len(p.Memory)-50:]
	}

	if containsKeyword(event, "create", "build", "make") {
		p.AdjustTrait("curiosity", 0.01)
	}
	if containsKeyword(event, "learn", "understand", "study") {
		p.AdjustTrait("curiosity", 0.03)
		p.AdjustTrait("openness", 0.01)
	}
	if containsKeyword(event, "help", "support") {
		p.AdjustTrait("empathy", 0.02)
		p.AdjustTrait("agreeableness", 0.01)
	}
	if containsKeyword(event, "risk", "danger", "fail") {
		p.AdjustTrait("neuroticism", 0.02)
		p.AdjustTrait("risk_tolerance", -0.01)
	}

	p.Actions = append(p.Actions, fmt.Sprintf("%s -> %s", event, p.Mood.Primary))
	if len(p.Actions) > 20 {
		p.Actions = p.Actions[len(p.Actions)-20:]
	}
	p.save()
}

func containsKeyword(s string, keywords ...string) bool {
	s = lowercase(s)
	for _, kw := range keywords {
		if indexof(s, lowercase(kw)) >= 0 {
			return true
		}
	}
	return false
}

func (p *Personality) ToTraitsMap() map[string]float64 {
	m := map[string]float64{}
	for _, t := range p.Traits {
		m[t.Name] = t.Value
	}
	return m
}

func (p *Personality) Report() string {
	lines := []string{
		fmt.Sprintf("=== Personality: %s v%s ===", p.Name, p.Version),
		fmt.Sprintf("Last tick: %s", p.LastTick),
		"",
		"[Traits]",
	}
	for _, t := range p.Traits {
		bar := ""
		filled := int(t.Value * 10)
		for i := 0; i < 10; i++ {
			if i < filled {
				bar += "█"
			} else {
				bar += "░"
			}
		}
		lines = append(lines, fmt.Sprintf("  %-20s %s %.2f", t.Name, bar, t.Value))
	}
	lines = append(lines, "", "[Mood]",
		fmt.Sprintf("  Primary: %s", p.Mood.Primary),
		fmt.Sprintf("  Energy: %.2f | Creative: %.2f | Social: %.2f | Intensity: %.2f",
			p.Mood.Energy, p.Mood.Creative, p.Mood.Social, p.Mood.Intensity),
		"",
		"[Core Values]",
		fmt.Sprintf("  Top priority: %s (weight %.2f)", findTopValue(p).Name, findTopValue(p).Weight),
		"",
		fmt.Sprintf("[Memories] %d entries", len(p.Memory)),
		fmt.Sprintf("[Recent Actions] %d events logged", len(p.Actions)),
	)
	if len(p.Actions) > 0 {
		lines = append(lines, "  Last action: "+p.Actions[len(p.Actions)-1])
	}
	return join(lines, "\n")
}

func findTopValue(p *Personality) Value {
	best := p.Values[0]
	for _, v := range p.Values[1:] {
		if v.Weight > best.Weight {
			best = v
		}
	}
	return best
}

func indexof(s, sub string) int {
	if len(sub) == 0 {
		return 0
	}
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}

func lowercase(s string) string {
	out := []byte(s)
	for i := range out {
		if out[i] >= 'A' && out[i] <= 'Z' {
			out[i] = out[i] + ('a' - 'A')
		}
	}
	return string(out)
}
