#!/bin/bash
# Tawiza CLI bash completion
# Install: source /path/to/tawiza.bash
# Or copy to: /etc/bash_completion.d/tawiza

_tawiza_completion() {
    local cur prev words cword

    # Fallback if bash-completion not installed
    if type _init_completion &>/dev/null; then
        _init_completion || return
    else
        COMPREPLY=()
        cur="${COMP_WORDS[COMP_CWORD]}"
        prev="${COMP_WORDS[COMP_CWORD-1]}"
        words=("${COMP_WORDS[@]}")
        cword=$COMP_CWORD
    fi

    # Main commands
    local main_commands="status chat run pro --help --version"

    # Pro subcommands
    local pro_commands="agent-list model-list model-pull gpu-status gpu-info gpu-benchmark gpu-monitor gpu-passthrough-status gpu-passthrough-enable gpu-passthrough-disable gpu-vm-list ollama-start ollama-stop data-import data-export data-list data-delete train-start train-status train-stop train-delete logs-show logs-clear metrics-export config-show config-set config-reset config-edit config-path cache-clear cache-info update-check doctor info"

    # Agents
    local agents="analyst coder browser ml writer researcher"

    case "${prev}" in
        tawiza)
            COMPREPLY=($(compgen -W "${main_commands}" -- "${cur}"))
            return 0
            ;;
        pro)
            COMPREPLY=($(compgen -W "${pro_commands}" -- "${cur}"))
            return 0
            ;;
        run)
            COMPREPLY=($(compgen -W "${agents}" -- "${cur}"))
            return 0
            ;;
        -m|--model)
            # Dynamic model completion from Ollama
            local models=$(curl -s http://localhost:11434/api/tags 2>/dev/null | grep -oP '"name":"\K[^"]+' || echo "qwen3:14b llama3:8b mistral:latest")
            COMPREPLY=($(compgen -W "${models}" -- "${cur}"))
            return 0
            ;;
        -d|--data)
            # Complete data files
            COMPREPLY=($(compgen -f -X '!*.@(csv|json|jsonl|parquet)' -- "${cur}"))
            return 0
            ;;
        model-pull)
            # Suggest common models
            local suggested_models="qwen3:14b qwen3:30b llama3:8b llama3:70b mistral:latest codellama:13b phi3:mini"
            COMPREPLY=($(compgen -W "${suggested_models}" -- "${cur}"))
            return 0
            ;;
        config-set|config-show)
            # Complete config keys
            local config_keys="model ollama_url gpu_enabled cache_enabled cache_ttl history_enabled history_limit theme language verbose timeout"
            COMPREPLY=($(compgen -W "${config_keys}" -- "${cur}"))
            return 0
            ;;
        data-import)
            # Complete data files
            COMPREPLY=($(compgen -f -X '!*.@(csv|json|jsonl|parquet)' -- "${cur}"))
            return 0
            ;;
        gpu-passthrough-enable)
            # Complete PCI addresses
            local pci_addrs=$(lspci -nn 2>/dev/null | grep -E 'VGA|3D' | awk '{print $1}')
            COMPREPLY=($(compgen -W "${pci_addrs}" -- "${cur}"))
            return 0
            ;;
        train-status|train-stop|train-delete)
            # Complete job IDs
            local jobs=$(cat ~/.tawiza/jobs.json 2>/dev/null | grep -oP '"\K[0-9_]+(?=":)' || echo "")
            COMPREPLY=($(compgen -W "${jobs}" -- "${cur}"))
            return 0
            ;;
    esac

    # Handle options
    case "${cur}" in
        -*)
            local opts="--help -h --verbose -v --model -m --task -t --data -d --force -f --interactive --no-interactive"
            COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
            return 0
            ;;
    esac

    # Default: complete with main commands or files
    if [[ ${cword} -eq 1 ]]; then
        COMPREPLY=($(compgen -W "${main_commands}" -- "${cur}"))
    fi
}

# Register completion
complete -F _tawiza_completion tawiza

# Also support the python module invocation
complete -F _tawiza_completion "python -m src.cli.v2.app"
