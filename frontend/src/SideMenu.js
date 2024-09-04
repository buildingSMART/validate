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
import Divider from '@mui/material/Divider';

import { VERSION, COMMIT_HASH } from './environment';

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
                display: { xs:'none', md: 'flex'},
            }}
        >
            <Toolbar />
            <Box sx={{ overflow: 'auto' , paddingTop:'5vh'}}>
                <List>
                    {['Home', 'Dashboard'].map((text, index) => (
                        <ListItem key={text} disablePadding style={{ 'borderLeft': context.pageTitle === text.toLowerCase() ? 'thick solid #1976d2' : 'none' }}>
                            <ListItemButton href={text === "Home" ? context.sandboxId ? `/sandbox/${context.sandboxId}` : "/" : context.sandboxId ? `/sandbox/dashboard/${context.sandboxId}` : "/dashboard"}>
                                <ListItemIcon>
                                    {text === "Home" ? <HomeIcon /> : <CheckIcon />}
                                </ListItemIcon>
                                <ListItemText primary={text === "Dashboard" ? "Validation" : text} />
                            </ListItemButton>
                        </ListItem>
                    ))}
                </List>

                <List style={{ position: "absolute", bottom: "0", width: "100%" }}>
                <Divider />
                    <ListItem key={"test"} disablePadding>
                        <ListItemButton>
                            <ListItemText style={{ textAlign: 'center' }} primary={`${context["environment"]} ${VERSION || ''} ${COMMIT_HASH ? ' - #' + COMMIT_HASH : ''}`} />
                        </ListItemButton>
                    </ListItem>
                </List>
            </Box>
        </Drawer>
    )
}