project_dir="${CLAUDE_PROJECT_DIR:-$PWD}"

find "$project_dir" \
  -type d \
  -name '.cc-writes' \
  -path '*/.claude/.cc-writes' \
  -prune \
  -exec rm -rf -- {} +

find "$project_dir" \
  -depth \
  -type d \
  -name '.claude' \
  -empty \
  -delete
