set -gx EDITOR micro

if status is-interactive
    abbr -a up "sudo dnf upgrade --refresh"
    abbr -a upclean "sudo dnf upgrade --refresh && sudo dnf autoremove"
end

function fish_greeting
    fastfetch
end
