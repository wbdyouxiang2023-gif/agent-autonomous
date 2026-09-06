package main

import (
	"fmt"
	"math/rand"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		printUsage()
		return
	}
	switch os.Args[1] {
	case "personality":
		handlePersonality()
	case "decision":
		handleDecision()
	case "creator":
		handleCreator()
	case "dashboard":
		handleDashboard()
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n", os.Args[1])
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println(`Digital Creator Workspace CLI
==============================
Commands:
  personality [--name NAME] [--act TEXT]  Show/interact with personality
  decision [--context TEXT]               Run autonomous decision cycle
  creator                                 Show creator stats and reports
  dashboard                               Print full system dashboard`)
}

func handlePersonality() {
	name := "AURA"
	act := ""
	for i := 2; i < len(os.Args); i++ {
		switch os.Args[i] {
		case "--name":
			if i+1 < len(os.Args) {
				name = os.Args[i+1]
				i++
			}
		case "--act":
			if i+1 < len(os.Args) {
				act = os.Args[i+1]
				i++
			}
		}
	}
	p := NewPersonality(name)
	p.Tick()
	if act != "" {
		p.Reflect(act)
	}
	fmt.Println(p.Report())
}

func handleDecision() {
	var ctxText string
	for i := 2; i < len(os.Args); i++ {
		if os.Args[i] == "--context" && i+1 < len(os.Args) {
			ctxText = os.Args[i+1]
			i++
		}
	}
	ctx := Context{
		Tasks:       []string{},
		Resources:   0.7 + rand.Float64()*0.2,
		TimeLeft:    0.8,
		Stress:      0.2 + rand.Float64()*0.2,
		Opportunity: 0.5 + rand.Float64()*0.4,
	}
	if ctxText != "" {
		ctx.Tasks = append(ctx.Tasks, ctxText)
	}
	traits := map[string]float64{
		"creative":          0.8,
		"curiosity":         0.9,
		"openness":          0.75,
		"empathy":           0.85,
		"risk_tolerance":    0.5,
		"conscientiousness": 0.7,
	}
	engine := NewEngine()
	d := engine.Decide(ctx, traits)
	fmt.Printf("Decision #%d: %s\n", d.ID, d.Chosen)
	fmt.Printf("Reason: %s\n", d.Reason)
	fmt.Printf("Confidence: %.2f | Category: %s\n", d.Confidence, d.Category)
	fmt.Println("\n" + engine.Report())
}

func handleCreator() {
	c := NewCreator()
	fmt.Println(c.Report())
	stats := c.Stats()
	fmt.Printf("\nAvg quality: %.2f | Artifacts: %d | Plans: %d\n",
		stats["avg_quality"], stats["total_artifacts"].(int), stats["total_plans"].(int))
}

func handleDashboard() {
	fmt.Println("============================================================")
	fmt.Println("        Digital Creator Workspace - Dashboard")
	fmt.Println("============================================================")
	fmt.Println()

	p := NewPersonality("AURA")
	p.Tick()
	fmt.Println("--- AI PERSONALITY ---")
	fmt.Println(p.Report())
	fmt.Println()

	engine := NewEngine()
	d := engine.Decide(Context{Resources: 0.8, Stress: 0.3},
		map[string]float64{"creative": 0.8, "curiosity": 0.9})
	fmt.Printf("Latest Decision: %s (confidence: %.2f)\n", d.Chosen, d.Confidence)
	fmt.Println(engine.Report())
	fmt.Println()

	c := NewCreator()
	fmt.Println("--- DIGITAL CREATOR ---")
	fmt.Println(c.Report())

	fmt.Println()
	fmt.Println("============================================================")
}
