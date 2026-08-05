set -gx EDITOR micro

if status is-interactive
    abbr -a up "sudo dnf upgrade --refresh"
    abbr -a upclean "sudo dnf upgrade --refresh && sudo dnf autoremove"
end

function fish_greeting
    fastfetch

    echo ""
    set_color -o blue
    echo "Quick commands:"
    set_color green
    echo -n "  up      "
    set_color normal
    echo "-> update packages (dnf upgrade)"
    set_color green
    echo -n "  upclean "
    set_color normal
    echo "-> update and clean up (dnf autoremove)"
    echo ""
end
