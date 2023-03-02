import * as React from 'react';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import Toolbar from '@mui/material/Toolbar';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import HomeIcon from '@mui/icons-material/Home';
import CheckIcon from '@mui/icons-material/Check';

import { PageContext } from './Page';
import { useContext } from 'react';

const drawerWidth = 240;

export default function SideMenu() {

    const context = useContext(PageContext);
    return (
        <Drawer
            variant="permanent"
            sx={{
                width: drawerWidth,
                flexShrink: 0,
                [`& .MuiDrawer-paper`]: { width: drawerWidth, boxSizing: 'border-box' },
            }}
        >
            <Toolbar />
            <Box sx={{ overflow: 'auto' }}>
                <List>
                    {['Home', 'Validation'].map((text, index) => (
                        <ListItem key={text} disablePadding>
                            <ListItemButton href={text === "Home" ? context.sandboxId ? `/sandbox/${context.sandboxId}` : "/" : context.sandboxId ? `/sandbox/dashboard/${context.sandboxId}` : "/dashboard"}>
                                <ListItemIcon>
                                    {text === "Home" ? <HomeIcon /> : <CheckIcon />}
                                </ListItemIcon>
                                <ListItemText primary={text} />
                            </ListItemButton>
                        </ListItem>
                    ))}
                </List>

                <List style={{ position: "absolute", bottom: "0", width: "100%" }}>
                    <ListItem key={"test"} disablePadding>
                        <ListItemButton>
                            <ListItemText style={{ textAlign: 'center' }} primary={`${context["environment"]} v0.5.1`} />
                        </ListItemButton>
                    </ListItem>
                </List>
            </Box>
        </Drawer>
    )
}