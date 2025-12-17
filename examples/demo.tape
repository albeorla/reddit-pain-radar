# VHS tape file for Pain Radar CLI demo
# https://github.com/charmbracelet/vhs

Output examples/demo.gif

Set Shell "zsh"
Set FontSize 14
Set Width 1000
Set Height 600
Set Padding 20

# Setup
Type "source .venv/bin/activate"
Enter
Sleep 500ms

# Clean start
Type "rm -f pain_radar.sqlite3 && pain-radar init-db"
Enter
Sleep 2s

# Show version
Type "pain-radar --version"
Enter
Sleep 1s

# Show available presets
Type "pain-radar sources"
Enter
Sleep 3s

# Add a preset (the new workflow!)
Type "pain-radar sources-add indie_saas"
Enter
Sleep 2s

# Fetch from source sets (no -s flag needed!)
Type "pain-radar fetch"
Enter
Sleep 10s

# Show stats
Type "pain-radar stats"
Enter
Sleep 2s

# Create a watchlist
Type 'pain-radar alerts-add "saas, startup, churn" --name "SaaS Pain"'
Enter
Sleep 2s

# Show help
Type "pain-radar --help"
Enter
Sleep 3s
