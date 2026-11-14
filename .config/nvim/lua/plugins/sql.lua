return {
  {
    "stevearc/conform.nvim",
    opts = {
      formatters = {
        sqlfluff = {
          cwd = function(self, ctx)
            return vim.fs.root(ctx.filename, ".git") or vim.fs.dirname(ctx.filename)
          end,
        },
      },
    },
  },
}
