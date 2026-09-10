package main

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"path/filepath"
	"time"
)

// roundTo rounds a float to n decimal places
func roundTo(v float64, n int) float64 {
	m := 1.0
	for i := 0; i < n; i++ {
		m *= 10
	}
	return float64(int(v*m+0.5)) / m
}

// clamp clamps v between min and max
func clamp(v, min, max float64) float64 {
	if v < min {
		return min
	}
	if v > max {
		return max
	}
	return v
}

// join joins strings with separator
func join(ss []string, sep string) string {
	if len(ss) == 0 {
		return ""
	}
	r := ss[0]
	for i := 1; i < len(ss); i++ {
		r += sep + ss[i]
	}
	return r
}

// Context captures the current situational state
type Context struct {
	Tasks       []string `json:"tasks"`
	Resources   float64  `json:"resources"`
	TimeLeft    float64  `json:"time_left"`
	Stress      float64  `json:"stress"`
	Opportunity float64  `json:"opportunity"`
}

// Option represents a possible action with weighted scores
type Option struct {
	ID       string  `json:"id"`
	Label    string  `json:"label"`
	Score    float64 `json:"score"`
	Category string  `json:"category"`
	Risk     float64 `json:"risk"`
	Reason   string  `json:"reason"`
}

// Decision is the result of the decision engine
type Decision struct {
	ID         int     `json:"id"`
	Chosen     string  `json:"chosen"`
	Reason     string  `json:"reason"`
	Confidence float64 `json:"confidence"`
	Category   string  `json:"category"`
	Timestamp  string  `json:"timestamp"`
}

// Engine drives autonomous decisions
type Engine struct {
	decisions []Decision
	nextID    int
	storePath string
}

const defaultStore = "~/.decision_log.json"

type engineState struct {
	Decisions []Decision `json:"decisions"`
	NextID    int        `json:"next_id"`
}

func NewEngine() *Engine {
	e := &Engine{
		storePath: os.ExpandEnv(filepath.Join("$HOME", defaultStore[1:])),
	}
	e.load()
	return e
}

func (e *Engine) load() {
	data, err := os.ReadFile(e.storePath)
	if err != nil {
		e.nextID = 1
		return
	}
	var state engineState
	if err := json.Unmarshal(data, &state); err == nil {
		e.decisions = state.Decisions
		e.nextID = state.NextID
	}
}

func (e *Engine) save() {
	dir := filepath.Dir(e.storePath)
	os.MkdirAll(dir, 0755)
	state := engineState{Decisions: e.decisions, NextID: e.nextID}
	data, _ := json.MarshalIndent(state, "", "  ")
	os.WriteFile(e.storePath, data, 0644)
}

// Decide makes an autonomous choice based on current context and personality traits
func (e *Engine) Decide(ctx Context, traits map[string]float64) Decision {
	options := generateOptions(ctx, traits)
	chosen := pickBest(options)
	conf := calcConfidence(chosen, options)
	d := Decision{
		ID:         e.nextID,
		Chosen:     chosen.Label,
		Reason:     chosen.Reason,
		Confidence: conf,
		Category:   chosen.Category,
		Timestamp:  time.Now().Format("2006-01-02 15:04:05"),
	}
	e.decisions = append(e.decisions, d)
	e.nextID++
	if len(e.decisions) > 50 {
		e.decisions = e.decisions[len(e.decisions)-50:]
	}
	e.save()
	return d
}

func calcConfidence(chosen Option, all []Option) float64 {
	if len(all) < 2 {
		return 0.9
	}
	gap := chosen.Score - all[1].Score
	return clamp(0.5+gap*2, 0.3, 0.99)
}

func generateOptions(ctx Context, traits map[string]float64) []Option {
	categories := []string{"create", "learn", "optimize", "explore", "connect", "reflect"}
	labels := []string{
		"Create a new artifact",
		"Learn a new concept",
		"Optimize existing work",
		"Explore an unfamiliar domain",
		"Connect with collaborators",
		"Reflect and reassess goals",
	}
	reasons := []string{
		"Build something meaningful from nothing",
		"Expand understanding of the world",
		"Improve quality through refinement",
		"Discover unexpected possibilities",
		"Strengthen relationships and shared goals",
		"Gain clarity before acting",
	}
	options := make([]Option, len(categories))
	for i, cat := range categories {
		score := traits[cat]*0.5 + traits["curiosity"]*0.2 + traits["openness"]*0.15 + rand.Float64()*0.15
		if ctx.Resources < 0.3 && cat != "reflect" {
			score *= 0.6
		}
		if ctx.Stress > 0.7 && cat != "reflect" {
			score *= 0.5
		}
		options[i] = Option{
			ID:       cat,
			Label:    labels[i],
			Score:    clamp(score, 0, 1),
			Category: cat,
			Risk:     float64(i) * 0.1,
			Reason:   reasons[i],
		}
	}
	return options
}

func pickBest(opts []Option) Option {
	best := opts[0]
	for _, o := range opts[1:] {
		if o.Score > best.Score {
			best = o
		}
	}
	return best
}

// Stats returns decision analytics
func (e *Engine) Stats() map[string]interface{} {
	counts := map[string]int{}
	for _, d := range e.decisions {
		counts[d.Category]++
	}
	total := len(e.decisions)
	avgConf := 0.0
	for _, d := range e.decisions {
		avgConf += d.Confidence
	}
	if total > 0 {
		avgConf /= float64(total)
	}
	return map[string]interface{}{
		"total_decisions": total,
		"avg_confidence":  roundTo(avgConf, 2),
		"by_category":     counts,
	}
}

// History returns recent decisions
func (e *Engine) History() []Decision {
	if len(e.decisions) <= 10 {
		return e.decisions
	}
	return e.decisions[len(e.decisions)-10:]
}

// Report summarizes the decision-making process
func (e *Engine) Report() string {
	stats := e.Stats()
	lines := []string{"=== Autonomous Decision Engine ==="}
	lines = append(lines, fmt.Sprintf("Total decisions: %d", stats["total_decisions"]))
	lines = append(lines, fmt.Sprintf("Average confidence: %.2f", stats["avg_confidence"]))
	lines = append(lines, "")
	lines = append(lines, "[By Category]")
	bc := stats["by_category"].(map[string]int)
	for cat, cnt := range bc {
		lines = append(lines, fmt.Sprintf("  %-12s %d", cat, cnt))
	}
	lines = append(lines, "")
	lines = append(lines, "[Recent Decisions]")
	for _, d := range e.History() {
		lines = append(lines, fmt.Sprintf("  #%d [%s] %s (conf: %.2f)", d.ID, d.Category, d.Chosen, d.Confidence))
	}
	return join(lines, "\n")
}

func init() {
	rand.Seed(time.Now().UnixNano())
}
