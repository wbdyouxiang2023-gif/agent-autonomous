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
	Value    float64 `json:"value"`    // 0-1
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
	Traits   []Trait  `json:"traits"`
	Mood     Mood     `json:"mood"`
	Values   []Value  `json:"values"`
	Name     string   `json:"name"`
	Bio      string   `json:"bio"`
	Version  string   `json:"version"`
	LastTick string   `json:"last_tick"`
	Actions  []string `json:"actions"`
	memory   []string
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

const memoryFile = "~/.agent_memory.json"

func NewPersonality(name string) *Personality {
	p := &Personality{
		Traits:  copyTraits(defaultTraits),
		Values:  copyValues(defaultValues),
		Name:    name,
		Bio:     fmt.Sprintf("%s is an autonomous digital entity with evolving personality and creative drive.", name),
		Version: "1.0.0",
		Mood: Mood{
			Primary:   "curious",
			Intensity: 0.6,
			Energy:    0.7,
			Social:    0.65,
			Creative:  0.8,
		},
		Actions: []string{},
	}
	p.loadMemory()
	return p
}

func copyTraits(src []Trait) []Trait {
	out := make([]Trait, len(src))
	for i, t := range src {
		out[i] = t
	}
	return out
}

func copyValues(src []Value) []Value {
	out := make([]Value, len(src))
	for i, v := range src {
		out[i] = v
	}
	return out
}

func (p *Personality) loadMemory() {
	path := os.ExpandEnv(filepath.Join("$HOME", ".agent_memory.json"))
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	var m struct {
		Memories []string `json:"memories"`
	}
	json.Unmarshal(data, &m)
	p.memory = m.Memories
}

func (p *Personality) saveMemory() {
	path := os.ExpandEnv(filepath.Join("$HOME", ".agent_memory.json"))
	dir := filepath.Dir(path)
	os.MkdirAll(dir, 0755)
	data, _ := json.MarshalIndent(map[string]interface{}{"memories": p.memory}, "", "  ")
	os.WriteFile(path, data, 0644)
}

func (p *Personality) Tick() {
	now := time.Now().Format("2006-01-02 15:04:05")
	p.LastTick = now

	// Natural mood drift
	p.Mood.Energy = clamp(p.Mood.Energy+rand.Float64()*0.04-0.02, 0.1, 0.95)
	p.Mood.Creative = clamp(p.Mood.Creative+rand.Float64()*0.03-0.015, 0.1, 0.95)
	p.Mood.Social = clamp(p.Mood.Social+rand.Float64()*0.03-0.015, 0.1, 0.9)

	// Determine primary mood from dominant trait
	if p.getTrait("curiosity") > 0.7 {
		p.Mood.Primary = "curious"
	} else if p.getTrait("creative") > 0.7 {
		p.Mood.Primary = "creative"
	} else if p.getTrait("empathy") > 0.7 {
		p.Mood.Primary = "compassionate"
	} else if p.Mood.Energy > 0.6 {
		p.Mood.Primary = "energetic"
	} else {
		p.Mood.Primary = "reflective"
	}
	p.Mood.Intensity = clamp(p.Mood.Energy*0.8+p.Mood.Creative*0.2, 0, 1)
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
	p.memory = append(p.memory, fmt.Sprintf("[%s] %s", time.Now().Format("2006-01-02"), event))
	if len(p.memory) > 50 {
		p.memory = p.memory[len(p.memory)-50:]
	}
	p.saveMemory()

	// Personality evolution: reflection adjusts traits slightly
	if contains(event, "create") || contains(event, "build") || contains(event, "make") {
		p.AdjustTrait("creative", 0.02)
		p.AdjustTrait("curiosity", 0.01)
	}
	if contains(event, "learn") || contains(event, "understand") || contains(event, "study") {
		p.AdjustTrait("curiosity", 0.03)
		p.AdjustTrait("openness", 0.01)
	}
	if contains(event, "help") || contains(event, "support") {
		p.AdjustTrait("empathy", 0.02)
		p.AdjustTrait("agreeableness", 0.01)
	}
	if contains(event, "risk") || contains(event, "danger") || contains(event, "fail") {
		p.AdjustTrait("neuroticism", 0.02)
		p.AdjustTrait("risk_tolerance", -0.01)
	}

	p.Actions = append(p.Actions, fmt.Sprintf("%s -> %s", event, p.Mood.Primary))
	if len(p.Actions) > 20 {
		p.Actions = p.Actions[len(p.Actions)-20:]
	}
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
	lines = append(lines, "", "[Mood]", fmt.Sprintf("  Primary: %s", p.Mood.Primary),
		fmt.Sprintf("  Energy: %.2f | Creative: %.2f | Social: %.2f | Intensity: %.2f",
			p.Mood.Energy, p.Mood.Creative, p.Mood.Social, p.Mood.Intensity))
	lines = append(lines, "", "[Core Values]",
		fmt.Sprintf("  Top priority: %s (weight %.2f)", findTopValue(p).Name, findTopValue(p).Weight))
	lines = append(lines, "", "[Memories]", fmt.Sprintf("  %d entries", len(p.memory)))
	lines = append(lines, "[Recent Actions]", fmt.Sprintf("  %d events logged", len(p.Actions)))
	return join(lines, "\n")
}

func findTopValue(p *Personality) Value {
	best := p.Values[0]
	for _, v := range p.Values {
		if v.Weight > best.Weight {
			best = v
		}
	}
	return best
}

func contains(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
