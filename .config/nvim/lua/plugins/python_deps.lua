return {
  {
    "mhiro2/pydeps.nvim",
    ft = "toml",
    config = function()
      require("pydeps").setup()
    end,
  },
}
