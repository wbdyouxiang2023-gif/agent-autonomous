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
	case "save":
		handleSave()
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
  decision [--name NAME] [--context TEXT] Run autonomous decision cycle
  creator                                 Show creator stats and reports
  dashboard [--name NAME]                 Print full system dashboard
  save                                    Save current persona state
`)
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
	name := "AURA"
	var ctxText string
	for i := 2; i < len(os.Args); i++ {
		switch os.Args[i] {
		case "--name":
			if i+1 < len(os.Args) {
				name = os.Args[i+1]
				i++
			}
		case "--context":
			if i+1 < len(os.Args) {
				ctxText = os.Args[i+1]
				i++
			}
		}
	}
	p := NewPersonality(name)
	p.Tick()
	ctx := Context{
		Tasks:       []string{},
		Resources:   clamp(0.5+p.Mood.Energy*0.3, 0.2, 1.0),
		TimeLeft:    0.8,
		Stress:      clamp(0.1+p.getTrait("neuroticism")*0.3, 0.05, 0.8),
		Opportunity: clamp(p.Mood.Creative*0.5+rand.Float64()*0.2, 0.2, 1.0),
	}
	if ctxText != "" {
		ctx.Tasks = append(ctx.Tasks, ctxText)
	}
	engine := NewEngine()
	d := engine.Decide(ctx, p.ToTraitsMap())
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

func handleSave() {
	name := "AURA"
	for i := 2; i < len(os.Args); i++ {
		if os.Args[i] == "--name" && i+1 < len(os.Args) {
			name = os.Args[i+1]
			i++
		}
	}
	p := NewPersonality(name)
	p.Tick()
	p.save()
	fmt.Printf("Saved personality: %s\n", p.Name)
	fmt.Printf("Traits: curiosity=%.2f empathy=%.2f creativity=%.2f\n",
		p.getTrait("curiosity"), p.getTrait("empathy"), p.getTrait("creative"))
	fmt.Printf("Memories: %d | Actions: %d\n", len(p.Memory), len(p.Actions))
}

func handleDashboard() {
	name := "AURA"
	for i := 2; i < len(os.Args); i++ {
		if os.Args[i] == "--name" && i+1 < len(os.Args) {
			name = os.Args[i+1]
			i++
		}
	}

	p := NewPersonality(name)
	p.Tick()

	fmt.Println("============================================================")
	fmt.Println("        Digital Creator Workspace - Dashboard")
	fmt.Println("============================================================")
	fmt.Println()

	fmt.Println("--- AI PERSONALITY ---")
	fmt.Println(p.Report())
	fmt.Println()

	engine := NewEngine()
	d := engine.Decide(Context{
		Resources:   clamp(0.5+p.Mood.Energy*0.3, 0.2, 1.0),
		Stress:      clamp(0.1+p.getTrait("neuroticism")*0.3, 0.05, 0.8),
		Opportunity: clamp(p.Mood.Creative*0.5+0.2, 0.2, 1.0),
	}, p.ToTraitsMap())
	fmt.Printf("Latest Decision: %s (confidence: %.2f)\n", d.Chosen, d.Confidence)
	fmt.Println(engine.Report())
	fmt.Println()

	c := NewCreator()
	fmt.Println("--- DIGITAL CREATOR ---")
	fmt.Println(c.Report())

	fmt.Println()
	fmt.Println("============================================================")
}
