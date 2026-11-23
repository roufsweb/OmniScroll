fn main() {
    slint_build::compile("ui/app.slint").unwrap();

    #[cfg(windows)]
    {
        let mut res = winres::WindowsResource::new();
        res.set_icon("icon.ico");
        res.set("ProductName", "OmniScroll Studio");
        res.set("FileDescription", "OmniScroll Nordic Walnut Desktop Studio");
        res.set("CompanyName", "roufsweb");
        res.compile().unwrap();
    }
}
