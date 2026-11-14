return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        codebook = { mason = false },
        ruff = { mason = false },
        basedpyright = {
          mason = false,
          settings = {
            basedpyright = {
              analysis = {
                diagnosticMode = "workspace",
                typeCheckingMode = "standard",
                autoSearchPaths = true,
                indexing = true,
                diagnosticSeverityOverrides = {
                  reportUnusedImport = "none",
                  reportUnusedVariable = "none",
                  reportDuplicateImport = "none",
                  reportMissingModuleSource = "none",
                  reportGeneralTypeIssues = "warning",
                  reportOptionalSubscript = "warning",
                  reportOptionalMemberAccess = "warning",
                  reportOptionalCall = "warning",
                },
              },
              disableOrganizeImports = true,
            },
          },
        },
      },
    },
  },
}
